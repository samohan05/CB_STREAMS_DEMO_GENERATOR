#!/usr/bin/env python3
"""Codebeamer Demo Generator
Domain   : Diagnostic Ultrasound Imaging
Generated: 2026-04-15

Streams Concept:
  Projects are created ONCE in the Initial Stream.
  Streams (Library->PL->Transform->Release) form a hierarchy via sourceStreamId.
  The SAME projects are ADDED to each stream, branching their tracker items.
  Each stream derives from an explicit parent:
    Library:   no parent (top-level)
    PL:        no parent (aggregates from multiple libraries)
    Transform: parent = specific PL stream
    Release:   parent = specific Transform stream

APIs used:
  v3 (Swagger): /cb/api/v3/...
    GET  /v3/streams/initial           -- fetch initial stream ID
    POST /v3/projects/{id}/trackers    -- create tracker
    POST /v3/trackers/{id}/items       -- create tracker item
    PUT  /v3/items/{id}/fields         -- set Verifies field (ChoiceFieldValue) on TC->REQ
    POST /v3/streams/stream            -- create stream (sourceStreamId for hierarchy)
    PUT  /v3/streams/{id}/projects     -- add project to stream (PUT not POST)
    GET  /v3/projects                  -- list projects (idempotency check)
    DELETE /v3/projects/{id}           -- delete project (--clean mode)
    GET  /v3/trackers/types            -- discover tracker type IDs
  v1 (Legacy REST): /cb/rest/...
    POST /rest/project                 -- create project (v3 has NO POST /projects)
    GET  /rest/projects                -- list projects (fallback)
  GET  /v3/items/{id}/fields           -- discover Verifies field ID
"""

import os, requests, time, sys, argparse
from requests.auth import HTTPBasicAuth

# ─── CLI flags ────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Codebeamer Demo Generator")
parser.add_argument("--dry-run", action="store_true", help="Print plan without making API calls")
parser.add_argument("--clean", action="store_true", help="Delete existing demo projects before recreating")
args = parser.parse_args()
DRY_RUN = args.dry_run
CLEAN   = args.clean

CB_URL = os.environ.get("CB_URL",  "") or "https://your-cb-instance.com"
USER   = os.environ.get("CB_USER", "") or ""
PASS   = os.environ.get("CB_PASS", "")  # NEVER hardcoded — always use env var

if not USER or not PASS:
    print("ERROR: Codebeamer credentials not set.")
    print("  Option 1: export CB_USER=<user> CB_PASS=<pass>")
    print("  Option 2: export CB_URL=<url> CB_USER=<user> CB_PASS=<pass>")
    sys.exit(1)

REQ_TYPE_ID          = 5    # Requirements tracker type
TC_TYPE_ID           = 102  # Test Cases tracker type
VERIFIES_FIELD_ID    = 17   # 'Verifies' field (ChoiceFieldValue) on Test Cases tracker
STREAM_COLOR         = "#336699"  # required field in CreateStream schema

AUTH    = HTTPBasicAuth(USER, PASS)
HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}
BASE    = f"{CB_URL}/cb/api"       # v3 API (trackers, items, streams)
BASE_V1 = f"{CB_URL}/cb/rest"      # v1 legacy API (project creation — v3 has no POST /projects)

MAX_RETRIES    = 4
BACKOFF_BASE   = 1.0
RETRY_STATUSES = {429, 500, 502, 503, 504}

def _request(method, path, body=None):
    """Unified HTTP caller with exponential-backoff retry on 429 / 5xx."""
    url = f"{BASE}{path}"
    for attempt in range(MAX_RETRIES + 1):
        kwargs = {"auth": AUTH, "headers": HEADERS}
        if body is not None:
            kwargs["json"] = body
        r = getattr(requests, method)(url, **kwargs)
        if r.status_code not in RETRY_STATUSES or attempt == MAX_RETRIES:
            r.raise_for_status()
            return r.json() if r.content else None
        wait = BACKOFF_BASE * (2 ** attempt)
        if r.status_code == 429:
            try: wait = float(r.headers.get("Retry-After", wait))
            except (ValueError, TypeError): pass
        print(f"  … {r.status_code} on {method.upper()} {path} — retry {attempt+1}/{MAX_RETRIES} in {wait:.1f}s")
        time.sleep(wait)
    return None

def _get(path):           return _request("get", path)
def _post(path, body):    return _request("post", path, body)
def _put(path, body):     return _request("put", path, body)
def _delete(path):        return _request("delete", path)

def _request_v1(method, path, body=None):
    """Like _request but against the legacy v1 REST API (BASE_V1)."""
    url = f"{BASE_V1}{path}"
    for attempt in range(MAX_RETRIES + 1):
        fn = getattr(requests, method)
        kwargs = {"auth": AUTH, "headers": HEADERS}
        if body is not None:
            kwargs["json"] = body
        r = fn(url, **kwargs)
        if r.status_code not in RETRY_STATUSES:
            r.raise_for_status()
            try:
                return r.json()
            except Exception:
                return None
        wait = BACKOFF_BASE * (2 ** attempt)
        if r.status_code == 429:
            try: wait = float(r.headers.get("Retry-After", wait))
            except (ValueError, TypeError): pass
        print(f"  … {r.status_code} on {method.upper()} {path} — retry {attempt+1}/{MAX_RETRIES} in {wait:.1f}s")
        time.sleep(wait)
    return None

def _get_v1(path):         return _request_v1("get", path)
def _post_v1(path, body):  return _request_v1("post", path, body)

def ok(msg):   print(f"  + {msg}")
def warn(msg): print(f"  ! {msg}")

# ─── Auto-discovery ─────────────────────────────────────────────────────────
def discover_tracker_types():
    """GET /v3/trackers/types — scan for Requirement and Test Case type IDs."""
    try:
        types = _get("/v3/trackers/types")
        if isinstance(types, dict):
            types = types.get("types", types.get("items", []))
        req_id, tc_id = None, None
        for t in types:
            name = (t.get("name") or "").lower()
            tid = t.get("id")
            if "requirement" in name and req_id is None:
                req_id = tid
            elif "test" in name and "case" in name and tc_id is None:
                tc_id = tid
        if req_id and tc_id:
            ok(f"[DISCOVER] Tracker types: REQ={req_id}, TC={tc_id}")
        return req_id, tc_id
    except Exception as e:
        warn(f"[DISCOVER] Could not fetch tracker types: {e}")
        return None, None

def discover_verifies_field(tc_tracker_id, project_id):
    """Create temp TC item, read fields, find Verifies field ID, delete temp item."""
    if not tc_tracker_id or not project_id:
        return None
    temp_id = None
    try:
        r = _post(f"/v3/trackers/{tc_tracker_id}/items", {
            "name": "_discover_verifies_temp",
            "description": "Temporary item for field discovery — safe to delete"
        })
        temp_id = r["id"]
        fields = _get(f"/v3/items/{temp_id}/fields")
        if isinstance(fields, dict):
            fields = fields.get("fieldValues", fields.get("fields", []))
        for f in fields:
            name = (f.get("name") or "").lower()
            if "verif" in name:
                fid = f.get("fieldId") or f.get("id")
                if fid:
                    ok(f"[DISCOVER] Verifies field ID = {fid}")
                    return fid
    except Exception as e:
        warn(f"[DISCOVER] Could not discover Verifies field: {e}")
    finally:
        if temp_id:
            try: _delete(f"/v3/items/{temp_id}")
            except Exception: pass
    return None

def find_project(key):
    """Scan for existing project matching keyName. Tries v3 first, falls back to v1."""
    # Try v3: GET /v3/projects
    try:
        projects = _get("/v3/projects")
        if isinstance(projects, dict):
            projects = projects.get("projects", projects.get("items", []))
        for p in projects:
            if p.get("keyName") == key or p.get("name", "").startswith(key):
                return p["id"]
    except Exception: pass
    # Fallback: v1 GET /rest/projects
    try:
        projects = _get_v1("/projects")
        if isinstance(projects, dict):
            projects = projects.get("projects", projects.get("items", []))
        if isinstance(projects, list):
            for p in projects:
                kn = p.get("keyName") or ""
                uri = p.get("uri") or ""
                if kn == key or p.get("name", "").startswith(key):
                    return p.get("id") or int(uri.rsplit("/", 1)[-1])
    except Exception: pass
    return None

def delete_project(pid):
    """DELETE project — tries v3 first, falls back to v1."""
    if DRY_RUN:
        ok(f"[DRY-RUN] Would delete project {pid}")
        return
    try:
        _delete(f"/v3/projects/{pid}")
        ok(f"[CLEAN] Deleted project {pid}")
    except Exception:
        try:
            _request_v1("delete", f"/project/{pid}")
            ok(f"[CLEAN] Deleted project {pid} (v1)")
        except Exception as e:
            warn(f"[CLEAN] Could not delete project {pid}: {e}")

def mk_project(name, key, desc=""):
    """Create project via v1 REST API (v3 has no POST /projects endpoint).
    Idempotent: reuses existing project if found."""
    existing = find_project(key[:8])
    if existing:
        if CLEAN:
            delete_project(existing)
        else:
            ok(f"[PROJECT] {name}  id={existing} (already exists, reusing)")
            return existing
    if DRY_RUN:
        ok(f"[DRY-RUN] Would create project: {name} [{key[:8]}]")
        return None
    try:
        r = _post_v1("/project", {"name": name, "keyName": key[:8], "description": desc or name})
        pid = r.get("id") if isinstance(r, dict) else None
        if not pid and isinstance(r, dict):
            # v1 may return uri like "/project/123"
            uri = r.get("uri", "")
            pid = int(uri.rsplit("/", 1)[-1]) if "/" in uri else None
        if pid:
            ok(f"[PROJECT] {name}  id={pid}")
            return pid
        else:
            warn(f"[PROJECT] {name}: unexpected response: {r}")
            return None
    except Exception as e:
        warn(f"[PROJECT] {name}: {e}")
        return None

def mk_tracker(project_id, name, key, type_id):
    """POST /v3/projects/{projectId}/trackers."""
    if not project_id: return None
    if DRY_RUN:
        ok(f"  [DRY-RUN] Would create tracker: {name} [{key[:8]}]")
        return None
    try:
        r = _post(f"/v3/projects/{project_id}/trackers",
                  {"name": name, "keyName": key[:8], "type": {"id": type_id}})
        ok(f"  [TRACKER] {name}  id={r['id']}")
        return r["id"]
    except Exception as e:
        warn(f"  [TRACKER] {name}: {e}")
        return None

def mk_item(tracker_id, name, desc=""):
    """POST /v3/trackers/{trackerId}/items."""
    if not tracker_id: return None
    if DRY_RUN:
        ok(f"    [DRY-RUN] Would create item: {name[:50]}")
        return None
    try:
        r = _post(f"/v3/trackers/{tracker_id}/items", {"name": name, "description": desc})
        return r["id"]
    except Exception as e:
        warn(f"    [ITEM] {name[:50]}: {e}")
        return None

def set_verifies(tc_id, req_id):
    """PUT /v3/items/{itemId}/fields — sets the Verifies field on a test case.
    Returns True on success, False on failure."""
    if not tc_id or not req_id: return False
    if DRY_RUN:
        ok(f"    [DRY-RUN] Would link TC {tc_id} --verifies--> REQ {req_id}")
        return True
    try:
        _put(f"/v3/items/{tc_id}/fields", {
            "fieldValues": [{
                "fieldId": VERIFIES_FIELD_ID,
                "name": "Verifies",
                "type": "ChoiceFieldValue",
                "values": [{"id": req_id, "type": "TrackerItemReference"}]
            }]
        })
        ok(f"    [VERIFIES] TC {tc_id} --verifies--> REQ {req_id}")
        return True
    except Exception as e:
        warn(f"    [VERIFIES] TC {tc_id} -> REQ {req_id}: {e}")
        return False

def mk_stream(name, desc="", source_id=None):
    """POST /v3/streams/stream — create stream with optional parent."""
    if DRY_RUN:
        parent_info = f"  parent={source_id}" if source_id else ""
        ok(f"[DRY-RUN] Would create stream: {name}{parent_info}")
        return None
    try:
        body = {"name": name, "color": STREAM_COLOR, "description": desc}
        if source_id:
            body["sourceStreamId"] = source_id
            body["isSourceStreamChecked"] = True
        r = _post("/v3/streams/stream", body)
        parent_info = f"  parent={source_id}" if source_id else ""
        ok(f"[STREAM] {name}  id={r['id']}{parent_info}")
        return r["id"]
    except Exception as e:
        warn(f"[STREAM] {name}: {e} -- create manually: ALM > Streams > New")
        return None

def mk_stream_project(stream_id, project_id, initial_stream_id):
    """PUT /v3/streams/{streamId}/projects — add existing project to stream."""
    if not stream_id or not project_id: return
    if DRY_RUN:
        ok(f"  [DRY-RUN] Would add project {project_id} to stream {stream_id}")
        return
    try:
        _put(f"/v3/streams/{stream_id}/projects", {
            "projectId":      project_id,
            "sourceStreamId": initial_stream_id,
            "addAllTrackers": True
        })
        ok(f"  [STREAM-PROJ] project {project_id} added to stream {stream_id}")
    except Exception as e:
        warn(f"  [STREAM-PROJ] p{project_id}->s{stream_id}: {e}")
print("=" * 58)
print(f"CB Demo: Diagnostic Ultrasound Imaging")
if DRY_RUN: print("  ** DRY-RUN MODE — no API calls will be made **")
if CLEAN:   print("  ** CLEAN MODE — existing projects will be deleted first **")
print("=" * 58)

if not DRY_RUN:
    print("\n[INIT] Fetching initial stream ID...")
    try:
        INITIAL_STREAM_ID = _get("/v3/streams/initial")
        if isinstance(INITIAL_STREAM_ID, dict):
            INITIAL_STREAM_ID = INITIAL_STREAM_ID.get("id", INITIAL_STREAM_ID)
        ok(f"Initial stream ID = {INITIAL_STREAM_ID}")
    except Exception as e:
        warn(f"Cannot fetch initial stream ID: {e}")
        sys.exit(1)
else:
    INITIAL_STREAM_ID = None
    ok("[DRY-RUN] Skipping initial stream fetch")

# ─── Auto-discover tracker type IDs and Verifies field ID ──────────────
if not DRY_RUN:
    print("\n[DISCOVER] Auto-detecting tracker types and field IDs...")
    _req_type, _tc_type = discover_tracker_types()
    if _req_type: REQ_TYPE_ID = _req_type
    if _tc_type:  TC_TYPE_ID  = _tc_type
    if not _req_type or not _tc_type:
        warn(f"Using defaults: REQ_TYPE_ID={REQ_TYPE_ID}, TC_TYPE_ID={TC_TYPE_ID}")
else:
    ok("[DRY-RUN] Skipping auto-discovery, using defaults")

_verifies_discovered = False

# ─── Execution tracking ────────────────────────────────────────────────
_counts = {"streams": 0, "projects": 0, "trackers": 0, "requirements": 0, "test_cases": 0, "verifies": 0, "stream_project_links": 0}
_errors = []

# Project key -> CB project ID mapping (Phase 1 populates, Phase 2 uses)
_project_ids = {}

# Stream key -> CB stream ID mapping (for parent_stream_key resolution)
_stream_ids = {}

# ══════════════════════════════════════════════════════════════════════
# PHASE 1: Create all projects (in Initial Stream)
# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 58)
print("PHASE 1: Creating Projects, Trackers, Requirements, Test Cases")
print("=" * 58)

# ── Project: Beamformer Subsystem Requirements ──
pid_BFMSYS = mk_project("Beamformer Subsystem Requirements", "BFMSYS", "System-level requirements for transmit/receive beamforming electronics")
if pid_BFMSYS:
    _counts["projects"] += 1
    _project_ids["BFMSYS"] = pid_BFMSYS
else: _errors.append(("project", "Beamformer Subsystem Requirements", "mk_project returned None"))
rtid_pid_BFMSYS = mk_tracker(pid_BFMSYS, "Requirements", "REQ", REQ_TYPE_ID)
if rtid_pid_BFMSYS: _counts["trackers"] += 1
else: _errors.append(("tracker", "Requirements for Beamformer Subsystem Requirements", "mk_tracker returned None"))
ttid_pid_BFMSYS = mk_tracker(pid_BFMSYS, "Test Cases", "TC", TC_TYPE_ID)
if ttid_pid_BFMSYS: _counts["trackers"] += 1
else: _errors.append(("tracker", "Test Cases for Beamformer Subsystem Requirements", "mk_tracker returned None"))
if not _verifies_discovered and ttid_pid_BFMSYS and not DRY_RUN:
    _vf = discover_verifies_field(ttid_pid_BFMSYS, pid_BFMSYS)
    if _vf: VERIFIES_FIELD_ID = _vf
    else: warn(f"Using default VERIFIES_FIELD_ID={VERIFIES_FIELD_ID}")
    _verifies_discovered = True
rid_pid_BFMSYS_0 = mk_item(rtid_pid_BFMSYS, "The beamformer shall support 128 independent channels with per-channel delay resolution of 5 ns per IEC 61157", "Ensures spatial resolution through precise wavefront steering across the transducer aperture.")
if rid_pid_BFMSYS_0: _counts["requirements"] += 1
else: _errors.append(("requirement", "The beamformer shall support 128 independent channels with p", "mk_item returned None"))
if rid_pid_BFMSYS_0:
    tcid_pid_BFMSYS_0_0 = mk_item(ttid_pid_BFMSYS, "Verify per-channel delay resolution across all 128 beamformer channels", "Measure individual channel delay accuracy using calibrated hydrophone array. Steps: 1. Connect beamformer to calibrated 128-element test transducer 2. Program focused beam at 40 mm depth on each channel 3. Capture per-channel transmit waveform with digital oscilloscope 4. Compute delay error relative to commanded value Expected: Per-channel delay e")
    if tcid_pid_BFMSYS_0_0: _counts["test_cases"] += 1
    if set_verifies(tcid_pid_BFMSYS_0_0, rid_pid_BFMSYS_0): _counts["verifies"] += 1
rid_pid_BFMSYS_1 = mk_item(rtid_pid_BFMSYS, "The beamformer shall achieve dynamic range of at least 110 dB per IEC 61391-1", "Supports visualization of both strong specular and weak diffuse echoes in tissue.")
if rid_pid_BFMSYS_1: _counts["requirements"] += 1
else: _errors.append(("requirement", "The beamformer shall achieve dynamic range of at least 110 d", "mk_item returned None"))
if rid_pid_BFMSYS_1:
    tcid_pid_BFMSYS_1_0 = mk_item(ttid_pid_BFMSYS, "Verify beamformer dynamic range using AIUM tissue-mimicking phantom", "Measure signal-to-noise floor ratio across full receive gain range. Steps: 1. Connect reference transducer to beamformer 2. Acquire echo from AIUM phantom at max and min gain 3. Compute peak signal to noise floor ratio in dB 4. Record across 3 focal depths Expected: Measured dynamic range at least 110 dB at all tested focal depths")
    if tcid_pid_BFMSYS_1_0: _counts["test_cases"] += 1
    if set_verifies(tcid_pid_BFMSYS_1_0, rid_pid_BFMSYS_1): _counts["verifies"] += 1

# ── Project: Beamformer Performance Validation ──
pid_BFMPERF = mk_project("Beamformer Performance Validation", "BFMPERF", "Performance and stress testing for beamformer under fault and edge conditions")
if pid_BFMPERF:
    _counts["projects"] += 1
    _project_ids["BFMPERF"] = pid_BFMPERF
else: _errors.append(("project", "Beamformer Performance Validation", "mk_project returned None"))
rtid_pid_BFMPERF = mk_tracker(pid_BFMPERF, "Requirements", "REQ", REQ_TYPE_ID)
if rtid_pid_BFMPERF: _counts["trackers"] += 1
else: _errors.append(("tracker", "Requirements for Beamformer Performance Validation", "mk_tracker returned None"))
ttid_pid_BFMPERF = mk_tracker(pid_BFMPERF, "Test Cases", "TC", TC_TYPE_ID)
if ttid_pid_BFMPERF: _counts["trackers"] += 1
else: _errors.append(("tracker", "Test Cases for Beamformer Performance Validation", "mk_tracker returned None"))
if not _verifies_discovered and ttid_pid_BFMPERF and not DRY_RUN:
    _vf = discover_verifies_field(ttid_pid_BFMPERF, pid_BFMPERF)
    if _vf: VERIFIES_FIELD_ID = _vf
    else: warn(f"Using default VERIFIES_FIELD_ID={VERIFIES_FIELD_ID}")
    _verifies_discovered = True
rid_pid_BFMPERF_0 = mk_item(rtid_pid_BFMPERF, "The beamformer shall complete a full 128-channel focus update within 2 microseconds per IEC 62127-1", "Ensures real-time focusing for high frame rate B-mode and Doppler acquisition.")
if rid_pid_BFMPERF_0: _counts["requirements"] += 1
else: _errors.append(("requirement", "The beamformer shall complete a full 128-channel focus updat", "mk_item returned None"))
if rid_pid_BFMPERF_0:
    tcid_pid_BFMPERF_0_0 = mk_item(ttid_pid_BFMPERF, "Verify focus update latency under continuous acquisition load", "Measure time from focus command to channel output update. Steps: 1. Configure continuous B-mode acquisition at 30 fps 2. Trigger focus depth change via test interface 3. Capture channel outputs with 500 MHz logic analyzer 4. Measure latency from command to last channel update Expected: Focus update latency does not exceed 2 microseconds for all 128")
    if tcid_pid_BFMPERF_0_0: _counts["test_cases"] += 1
    if set_verifies(tcid_pid_BFMPERF_0_0, rid_pid_BFMPERF_0): _counts["verifies"] += 1
rid_pid_BFMPERF_1 = mk_item(rtid_pid_BFMPERF, "The beamformer shall maintain channel-to-channel gain uniformity within 0.5 dB per IEC 61391-2", "Prevents image artifacts from uneven channel sensitivity across the aperture.")
if rid_pid_BFMPERF_1: _counts["requirements"] += 1
else: _errors.append(("requirement", "The beamformer shall maintain channel-to-channel gain unifor", "mk_item returned None"))
if rid_pid_BFMPERF_1:
    tcid_pid_BFMPERF_1_0 = mk_item(ttid_pid_BFMPERF, "Verify channel gain uniformity using uniform reflector target", "Measure gain variation across channels with flat plate reflector. Steps: 1. Position flat plate reflector at 50 mm depth 2. Acquire single-channel data for each of 128 channels 3. Compute peak amplitude per channel 4. Calculate max deviation from mean Expected: Channel-to-channel gain variation does not exceed 0.5 dB peak-to-peak")
    if tcid_pid_BFMPERF_1_0: _counts["test_cases"] += 1
    if set_verifies(tcid_pid_BFMPERF_1_0, rid_pid_BFMPERF_1): _counts["verifies"] += 1

# ── Project: Transducer Subsystem Requirements ──
pid_TXDSYS = mk_project("Transducer Subsystem Requirements", "TXDSYS", "Requirements for ultrasound transducer probes and acoustic coupling")
if pid_TXDSYS:
    _counts["projects"] += 1
    _project_ids["TXDSYS"] = pid_TXDSYS
else: _errors.append(("project", "Transducer Subsystem Requirements", "mk_project returned None"))
rtid_pid_TXDSYS = mk_tracker(pid_TXDSYS, "Requirements", "REQ", REQ_TYPE_ID)
if rtid_pid_TXDSYS: _counts["trackers"] += 1
else: _errors.append(("tracker", "Requirements for Transducer Subsystem Requirements", "mk_tracker returned None"))
ttid_pid_TXDSYS = mk_tracker(pid_TXDSYS, "Test Cases", "TC", TC_TYPE_ID)
if ttid_pid_TXDSYS: _counts["trackers"] += 1
else: _errors.append(("tracker", "Test Cases for Transducer Subsystem Requirements", "mk_tracker returned None"))
if not _verifies_discovered and ttid_pid_TXDSYS and not DRY_RUN:
    _vf = discover_verifies_field(ttid_pid_TXDSYS, pid_TXDSYS)
    if _vf: VERIFIES_FIELD_ID = _vf
    else: warn(f"Using default VERIFIES_FIELD_ID={VERIFIES_FIELD_ID}")
    _verifies_discovered = True
rid_pid_TXDSYS_0 = mk_item(rtid_pid_TXDSYS, "The transducer shall achieve center frequency tolerance within 10 percent of nominal per IEC 61157", "Ensures consistent imaging characteristics across manufactured probe units.")
if rid_pid_TXDSYS_0: _counts["requirements"] += 1
else: _errors.append(("requirement", "The transducer shall achieve center frequency tolerance with", "mk_item returned None"))
if rid_pid_TXDSYS_0:
    tcid_pid_TXDSYS_0_0 = mk_item(ttid_pid_TXDSYS, "Verify transducer center frequency using hydrophone measurement", "Measure acoustic output center frequency in water tank. Steps: 1. Mount transducer in degassed water bath at 22 C 2. Position calibrated hydrophone at 30 mm on beam axis 3. Acquire pulse spectrum using FFT analyzer 4. Determine -6 dB center frequency Expected: Measured center frequency within 10 percent of nominal rated frequency")
    if tcid_pid_TXDSYS_0_0: _counts["test_cases"] += 1
    if set_verifies(tcid_pid_TXDSYS_0_0, rid_pid_TXDSYS_0): _counts["verifies"] += 1
rid_pid_TXDSYS_1 = mk_item(rtid_pid_TXDSYS, "The transducer shall withstand 10000 connect/disconnect cycles without degradation per IEC 60601-2-37", "Ensures mechanical durability of the probe connector under clinical use.")
if rid_pid_TXDSYS_1: _counts["requirements"] += 1
else: _errors.append(("requirement", "The transducer shall withstand 10000 connect/disconnect cycl", "mk_item returned None"))
if rid_pid_TXDSYS_1:
    tcid_pid_TXDSYS_1_0 = mk_item(ttid_pid_TXDSYS, "Verify connector durability after 10000 insertion cycles", "Perform automated mating cycles and verify electrical continuity. Steps: 1. Mount transducer connector in automated cycling fixture 2. Execute 10000 insertion and removal cycles at rated speed 3. Measure contact resistance on all signal pins after cycling 4. Inspect connector housing for visible damage Expected: Contact resistance below 50 milliohm")
    if tcid_pid_TXDSYS_1_0: _counts["test_cases"] += 1
    if set_verifies(tcid_pid_TXDSYS_1_0, rid_pid_TXDSYS_1): _counts["verifies"] += 1

# ── Project: Transducer Performance Validation ──
pid_TXDPERF = mk_project("Transducer Performance Validation", "TXDPERF", "Acoustic output and safety validation for ultrasound transducer probes")
if pid_TXDPERF:
    _counts["projects"] += 1
    _project_ids["TXDPERF"] = pid_TXDPERF
else: _errors.append(("project", "Transducer Performance Validation", "mk_project returned None"))
rtid_pid_TXDPERF = mk_tracker(pid_TXDPERF, "Requirements", "REQ", REQ_TYPE_ID)
if rtid_pid_TXDPERF: _counts["trackers"] += 1
else: _errors.append(("tracker", "Requirements for Transducer Performance Validation", "mk_tracker returned None"))
ttid_pid_TXDPERF = mk_tracker(pid_TXDPERF, "Test Cases", "TC", TC_TYPE_ID)
if ttid_pid_TXDPERF: _counts["trackers"] += 1
else: _errors.append(("tracker", "Test Cases for Transducer Performance Validation", "mk_tracker returned None"))
if not _verifies_discovered and ttid_pid_TXDPERF and not DRY_RUN:
    _vf = discover_verifies_field(ttid_pid_TXDPERF, pid_TXDPERF)
    if _vf: VERIFIES_FIELD_ID = _vf
    else: warn(f"Using default VERIFIES_FIELD_ID={VERIFIES_FIELD_ID}")
    _verifies_discovered = True
rid_pid_TXDPERF_0 = mk_item(rtid_pid_TXDPERF, "The transducer shall not exceed spatial peak temporal average intensity of 720 mW/cm2 per IEC 62359", "Limits acoustic energy deposition to prevent tissue heating beyond safe thresholds.")
if rid_pid_TXDPERF_0: _counts["requirements"] += 1
else: _errors.append(("requirement", "The transducer shall not exceed spatial peak temporal averag", "mk_item returned None"))
if rid_pid_TXDPERF_0:
    tcid_pid_TXDPERF_0_0 = mk_item(ttid_pid_TXDPERF, "Verify ISPTA output intensity at maximum transmit power setting", "Measure spatial peak temporal average intensity with radiation force balance. Steps: 1. Configure system to maximum acoustic output mode 2. Position radiation force balance in degassed water 3. Measure acoustic power at maximum PRF and voltage 4. Compute ISPTA from beam profile and power data Expected: Measured ISPTA does not exceed 720 mW/cm2 at a")
    if tcid_pid_TXDPERF_0_0: _counts["test_cases"] += 1
    if set_verifies(tcid_pid_TXDPERF_0_0, rid_pid_TXDPERF_0): _counts["verifies"] += 1
rid_pid_TXDPERF_1 = mk_item(rtid_pid_TXDPERF, "The transducer surface temperature shall not exceed 43 C after 30 min contact per IEC 60601-2-37", "Prevents thermal injury to patient skin during prolonged scanning procedures.")
if rid_pid_TXDPERF_1: _counts["requirements"] += 1
else: _errors.append(("requirement", "The transducer surface temperature shall not exceed 43 C aft", "mk_item returned None"))
if rid_pid_TXDPERF_1:
    tcid_pid_TXDPERF_1_0 = mk_item(ttid_pid_TXDPERF, "Verify transducer surface temperature under sustained maximum output", "Monitor probe face temperature during 30-minute continuous operation. Steps: 1. Apply transducer to tissue-mimicking phantom at 37 C 2. Run maximum output B-mode continuously for 30 minutes 3. Record surface temperature via embedded thermocouple at 1 min intervals 4. Identify peak surface temperature Expected: Peak transducer surface temperature do")
    if tcid_pid_TXDPERF_1_0: _counts["test_cases"] += 1
    if set_verifies(tcid_pid_TXDPERF_1_0, rid_pid_TXDPERF_1): _counts["verifies"] += 1

# ── Project: Image Processing Subsystem Requirements ──
pid_IMGSYS = mk_project("Image Processing Subsystem Requirements", "IMGSYS", "Requirements for scan conversion, filtering, and display processing")
if pid_IMGSYS:
    _counts["projects"] += 1
    _project_ids["IMGSYS"] = pid_IMGSYS
else: _errors.append(("project", "Image Processing Subsystem Requirements", "mk_project returned None"))
rtid_pid_IMGSYS = mk_tracker(pid_IMGSYS, "Requirements", "REQ", REQ_TYPE_ID)
if rtid_pid_IMGSYS: _counts["trackers"] += 1
else: _errors.append(("tracker", "Requirements for Image Processing Subsystem Requirements", "mk_tracker returned None"))
ttid_pid_IMGSYS = mk_tracker(pid_IMGSYS, "Test Cases", "TC", TC_TYPE_ID)
if ttid_pid_IMGSYS: _counts["trackers"] += 1
else: _errors.append(("tracker", "Test Cases for Image Processing Subsystem Requirements", "mk_tracker returned None"))
if not _verifies_discovered and ttid_pid_IMGSYS and not DRY_RUN:
    _vf = discover_verifies_field(ttid_pid_IMGSYS, pid_IMGSYS)
    if _vf: VERIFIES_FIELD_ID = _vf
    else: warn(f"Using default VERIFIES_FIELD_ID={VERIFIES_FIELD_ID}")
    _verifies_discovered = True
rid_pid_IMGSYS_0 = mk_item(rtid_pid_IMGSYS, "The image processor shall render B-mode frames at minimum 30 fps for 512-line format per IEC 61391-1", "Ensures smooth real-time visualization for clinical diagnostic scanning.")
if rid_pid_IMGSYS_0: _counts["requirements"] += 1
else: _errors.append(("requirement", "The image processor shall render B-mode frames at minimum 30", "mk_item returned None"))
if rid_pid_IMGSYS_0:
    tcid_pid_IMGSYS_0_0 = mk_item(ttid_pid_IMGSYS, "Verify sustained B-mode frame rate at full 512-line resolution", "Measure actual display frame rate during clinical scanning scenario. Steps: 1. Configure 512-line B-mode with standard clinical preset 2. Scan tissue-mimicking phantom continuously for 60 seconds 3. Count rendered frames via GPU timing instrumentation 4. Compute average and minimum frame rate Expected: Average frame rate at least 30 fps with no sin")
    if tcid_pid_IMGSYS_0_0: _counts["test_cases"] += 1
    if set_verifies(tcid_pid_IMGSYS_0_0, rid_pid_IMGSYS_0): _counts["verifies"] += 1
rid_pid_IMGSYS_1 = mk_item(rtid_pid_IMGSYS, "The image processor shall achieve lateral measurement accuracy within 2 percent per IEC 61391-2", "Supports reliable clinical caliper measurements for diagnostic decisions.")
if rid_pid_IMGSYS_1: _counts["requirements"] += 1
else: _errors.append(("requirement", "The image processor shall achieve lateral measurement accura", "mk_item returned None"))
if rid_pid_IMGSYS_1:
    tcid_pid_IMGSYS_1_0 = mk_item(ttid_pid_IMGSYS, "Verify lateral caliper accuracy using AIUM resolution phantom", "Compare on-screen measurements to known phantom target distances. Steps: 1. Scan AIUM 100 mm resolution phantom with calibrated probe 2. Place calipers on 10 mm, 30 mm, and 50 mm lateral targets 3. Record displayed measurement for each target 4. Compute percentage error relative to known values Expected: Lateral measurement error does not exceed 2 ")
    if tcid_pid_IMGSYS_1_0: _counts["test_cases"] += 1
    if set_verifies(tcid_pid_IMGSYS_1_0, rid_pid_IMGSYS_1): _counts["verifies"] += 1

# ── Project: Image Processing Performance Validation ──
pid_IMGPERF = mk_project("Image Processing Performance Validation", "IMGPERF", "Performance validation for image pipeline latency and artifact rejection")
if pid_IMGPERF:
    _counts["projects"] += 1
    _project_ids["IMGPERF"] = pid_IMGPERF
else: _errors.append(("project", "Image Processing Performance Validation", "mk_project returned None"))
rtid_pid_IMGPERF = mk_tracker(pid_IMGPERF, "Requirements", "REQ", REQ_TYPE_ID)
if rtid_pid_IMGPERF: _counts["trackers"] += 1
else: _errors.append(("tracker", "Requirements for Image Processing Performance Validation", "mk_tracker returned None"))
ttid_pid_IMGPERF = mk_tracker(pid_IMGPERF, "Test Cases", "TC", TC_TYPE_ID)
if ttid_pid_IMGPERF: _counts["trackers"] += 1
else: _errors.append(("tracker", "Test Cases for Image Processing Performance Validation", "mk_tracker returned None"))
if not _verifies_discovered and ttid_pid_IMGPERF and not DRY_RUN:
    _vf = discover_verifies_field(ttid_pid_IMGPERF, pid_IMGPERF)
    if _vf: VERIFIES_FIELD_ID = _vf
    else: warn(f"Using default VERIFIES_FIELD_ID={VERIFIES_FIELD_ID}")
    _verifies_discovered = True
rid_pid_IMGPERF_0 = mk_item(rtid_pid_IMGPERF, "The image pipeline shall maintain end-to-end latency below 40 ms from acquisition to display per IEC 62304", "Ensures real-time feedback for interventional and guided procedures.")
if rid_pid_IMGPERF_0: _counts["requirements"] += 1
else: _errors.append(("requirement", "The image pipeline shall maintain end-to-end latency below 4", "mk_item returned None"))
if rid_pid_IMGPERF_0:
    tcid_pid_IMGPERF_0_0 = mk_item(ttid_pid_IMGPERF, "Verify end-to-end image pipeline latency using synchronized trigger", "Measure delay from transmit trigger to rendered frame appearance. Steps: 1. Connect transmit sync pulse to high-speed camera trigger 2. Capture display output with 240 fps camera 3. Measure frame count between sync pulse and first rendered frame 4. Convert to milliseconds using camera frame rate Expected: End-to-end latency from transmit to display")
    if tcid_pid_IMGPERF_0_0: _counts["test_cases"] += 1
    if set_verifies(tcid_pid_IMGPERF_0_0, rid_pid_IMGPERF_0): _counts["verifies"] += 1
rid_pid_IMGPERF_1 = mk_item(rtid_pid_IMGPERF, "The speckle reduction filter shall improve CNR by at least 1.5 dB without reducing resolution per IEC 61391-1", "Enhances tissue contrast while preserving diagnostic spatial detail.")
if rid_pid_IMGPERF_1: _counts["requirements"] += 1
else: _errors.append(("requirement", "The speckle reduction filter shall improve CNR by at least 1", "mk_item returned None"))
if rid_pid_IMGPERF_1:
    tcid_pid_IMGPERF_1_0 = mk_item(ttid_pid_IMGPERF, "Verify speckle reduction CNR improvement on contrast phantom", "Compare contrast-to-noise ratio with filter enabled and disabled. Steps: 1. Scan tissue-mimicking phantom with anechoic targets 2. Acquire frames with speckle filter OFF, measure CNR 3. Enable speckle filter, acquire frames, measure CNR 4. Verify lateral resolution unchanged via wire targets Expected: CNR improvement at least 1.5 dB with lateral re")
    if tcid_pid_IMGPERF_1_0: _counts["test_cases"] += 1
    if set_verifies(tcid_pid_IMGPERF_1_0, rid_pid_IMGPERF_1): _counts["verifies"] += 1

# ══════════════════════════════════════════════════════════════════════
# PHASE 2: Create Stream Hierarchy & Add Projects to Streams
# Library (top) -> PL (top) -> Transform (parent=PL) -> Release (parent=Transform)
# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 58)
print("PHASE 2: Creating Streams & Adding Projects")
print("=" * 58)

# -- LIBRARY STREAMS --
print("\n[LIB] LIBRARY STREAMS")
sid_LIB_BFM = mk_stream("Beamformer Subsystem Library", "Baseline requirements and validation for beamforming electronics.", None)
if sid_LIB_BFM:
    _counts["streams"] += 1
    _stream_ids["LIB_BFM"] = sid_LIB_BFM
else: _errors.append(("stream", "Beamformer Subsystem Library", "mk_stream returned None"))
if _project_ids.get("BFMSYS") and sid_LIB_BFM:
    mk_stream_project(sid_LIB_BFM, _project_ids["BFMSYS"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("BFMPERF") and sid_LIB_BFM:
    mk_stream_project(sid_LIB_BFM, _project_ids["BFMPERF"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1

sid_LIB_TXD = mk_stream("Transducer Subsystem Library", "Baseline requirements and validation for ultrasound transducer probes.", None)
if sid_LIB_TXD:
    _counts["streams"] += 1
    _stream_ids["LIB_TXD"] = sid_LIB_TXD
else: _errors.append(("stream", "Transducer Subsystem Library", "mk_stream returned None"))
if _project_ids.get("TXDSYS") and sid_LIB_TXD:
    mk_stream_project(sid_LIB_TXD, _project_ids["TXDSYS"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("TXDPERF") and sid_LIB_TXD:
    mk_stream_project(sid_LIB_TXD, _project_ids["TXDPERF"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1

sid_LIB_IMG = mk_stream("Image Processing Subsystem Library", "Baseline requirements and validation for scan conversion and display.", None)
if sid_LIB_IMG:
    _counts["streams"] += 1
    _stream_ids["LIB_IMG"] = sid_LIB_IMG
else: _errors.append(("stream", "Image Processing Subsystem Library", "mk_stream returned None"))
if _project_ids.get("IMGSYS") and sid_LIB_IMG:
    mk_stream_project(sid_LIB_IMG, _project_ids["IMGSYS"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("IMGPERF") and sid_LIB_IMG:
    mk_stream_project(sid_LIB_IMG, _project_ids["IMGPERF"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1

# -- PRODUCT LINE STREAMS --
print("\n[PL] PRODUCT LINE STREAMS")
sid_PL_CART = mk_stream("Cart-Based Ultrasound Product Line", "Aggregated view for premium cart-based diagnostic ultrasound platforms.", None)
if sid_PL_CART:
    _counts["streams"] += 1
    _stream_ids["PL_CART"] = sid_PL_CART
else: _errors.append(("stream", "Cart-Based Ultrasound Product Line", "mk_stream returned None"))
if _project_ids.get("BFMSYS") and sid_PL_CART:
    mk_stream_project(sid_PL_CART, _project_ids["BFMSYS"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("BFMPERF") and sid_PL_CART:
    mk_stream_project(sid_PL_CART, _project_ids["BFMPERF"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("TXDSYS") and sid_PL_CART:
    mk_stream_project(sid_PL_CART, _project_ids["TXDSYS"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("TXDPERF") and sid_PL_CART:
    mk_stream_project(sid_PL_CART, _project_ids["TXDPERF"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("IMGSYS") and sid_PL_CART:
    mk_stream_project(sid_PL_CART, _project_ids["IMGSYS"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("IMGPERF") and sid_PL_CART:
    mk_stream_project(sid_PL_CART, _project_ids["IMGPERF"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1

sid_PL_POC = mk_stream("Point-of-Care Ultrasound Product Line", "Aggregated view for compact point-of-care ultrasound systems.", None)
if sid_PL_POC:
    _counts["streams"] += 1
    _stream_ids["PL_POC"] = sid_PL_POC
else: _errors.append(("stream", "Point-of-Care Ultrasound Product Line", "mk_stream returned None"))
if _project_ids.get("BFMSYS") and sid_PL_POC:
    mk_stream_project(sid_PL_POC, _project_ids["BFMSYS"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("BFMPERF") and sid_PL_POC:
    mk_stream_project(sid_PL_POC, _project_ids["BFMPERF"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("TXDSYS") and sid_PL_POC:
    mk_stream_project(sid_PL_POC, _project_ids["TXDSYS"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("TXDPERF") and sid_PL_POC:
    mk_stream_project(sid_PL_POC, _project_ids["TXDPERF"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("IMGSYS") and sid_PL_POC:
    mk_stream_project(sid_PL_POC, _project_ids["IMGSYS"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("IMGPERF") and sid_PL_POC:
    mk_stream_project(sid_PL_POC, _project_ids["IMGPERF"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1

# -- TRANSFORM STREAMS --
print("\n[TR] TRANSFORM STREAMS")
sid_TR_PREM = mk_stream("Premium Cart Platform Transform", "Adapts cart product line for high-end shared service configuration.", _stream_ids.get("PL_CART"))
if sid_TR_PREM:
    _counts["streams"] += 1
    _stream_ids["TR_PREM"] = sid_TR_PREM
else: _errors.append(("stream", "Premium Cart Platform Transform", "mk_stream returned None"))
if _project_ids.get("BFMSYS") and sid_TR_PREM:
    mk_stream_project(sid_TR_PREM, _project_ids["BFMSYS"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("BFMPERF") and sid_TR_PREM:
    mk_stream_project(sid_TR_PREM, _project_ids["BFMPERF"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("TXDSYS") and sid_TR_PREM:
    mk_stream_project(sid_TR_PREM, _project_ids["TXDSYS"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("TXDPERF") and sid_TR_PREM:
    mk_stream_project(sid_TR_PREM, _project_ids["TXDPERF"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("IMGSYS") and sid_TR_PREM:
    mk_stream_project(sid_TR_PREM, _project_ids["IMGSYS"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("IMGPERF") and sid_TR_PREM:
    mk_stream_project(sid_TR_PREM, _project_ids["IMGPERF"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1

sid_TR_CMPCT = mk_stream("Compact Handheld Transform", "Adapts POC product line for handheld battery-powered operation.", _stream_ids.get("PL_POC"))
if sid_TR_CMPCT:
    _counts["streams"] += 1
    _stream_ids["TR_CMPCT"] = sid_TR_CMPCT
else: _errors.append(("stream", "Compact Handheld Transform", "mk_stream returned None"))
if _project_ids.get("BFMSYS") and sid_TR_CMPCT:
    mk_stream_project(sid_TR_CMPCT, _project_ids["BFMSYS"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("BFMPERF") and sid_TR_CMPCT:
    mk_stream_project(sid_TR_CMPCT, _project_ids["BFMPERF"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("TXDSYS") and sid_TR_CMPCT:
    mk_stream_project(sid_TR_CMPCT, _project_ids["TXDSYS"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("TXDPERF") and sid_TR_CMPCT:
    mk_stream_project(sid_TR_CMPCT, _project_ids["TXDPERF"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("IMGSYS") and sid_TR_CMPCT:
    mk_stream_project(sid_TR_CMPCT, _project_ids["IMGSYS"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("IMGPERF") and sid_TR_CMPCT:
    mk_stream_project(sid_TR_CMPCT, _project_ids["IMGPERF"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1

# -- RELEASE / VARIANT STREAMS --
print("\n[REL] RELEASE / VARIANT STREAMS")
sid_REL_EX90 = mk_stream("EchoVista EX90 Release", "Release stream for premium cart-based radiology ultrasound system.", _stream_ids.get("TR_PREM"))
if sid_REL_EX90:
    _counts["streams"] += 1
    _stream_ids["REL_EX90"] = sid_REL_EX90
else: _errors.append(("stream", "EchoVista EX90 Release", "mk_stream returned None"))
if _project_ids.get("BFMSYS") and sid_REL_EX90:
    mk_stream_project(sid_REL_EX90, _project_ids["BFMSYS"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("BFMPERF") and sid_REL_EX90:
    mk_stream_project(sid_REL_EX90, _project_ids["BFMPERF"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("TXDSYS") and sid_REL_EX90:
    mk_stream_project(sid_REL_EX90, _project_ids["TXDSYS"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("TXDPERF") and sid_REL_EX90:
    mk_stream_project(sid_REL_EX90, _project_ids["TXDPERF"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("IMGSYS") and sid_REL_EX90:
    mk_stream_project(sid_REL_EX90, _project_ids["IMGSYS"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("IMGPERF") and sid_REL_EX90:
    mk_stream_project(sid_REL_EX90, _project_ids["IMGPERF"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1

sid_REL_EX50 = mk_stream("EchoVista EX50 Release", "Release stream for mid-tier cart-based general imaging system.", _stream_ids.get("TR_PREM"))
if sid_REL_EX50:
    _counts["streams"] += 1
    _stream_ids["REL_EX50"] = sid_REL_EX50
else: _errors.append(("stream", "EchoVista EX50 Release", "mk_stream returned None"))
if _project_ids.get("BFMSYS") and sid_REL_EX50:
    mk_stream_project(sid_REL_EX50, _project_ids["BFMSYS"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("BFMPERF") and sid_REL_EX50:
    mk_stream_project(sid_REL_EX50, _project_ids["BFMPERF"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("TXDSYS") and sid_REL_EX50:
    mk_stream_project(sid_REL_EX50, _project_ids["TXDSYS"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("TXDPERF") and sid_REL_EX50:
    mk_stream_project(sid_REL_EX50, _project_ids["TXDPERF"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("IMGSYS") and sid_REL_EX50:
    mk_stream_project(sid_REL_EX50, _project_ids["IMGSYS"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("IMGPERF") and sid_REL_EX50:
    mk_stream_project(sid_REL_EX50, _project_ids["IMGPERF"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1

sid_REL_HP10 = mk_stream("HandiPulse HP10 Release", "Release stream for handheld wireless point-of-care ultrasound.", _stream_ids.get("TR_CMPCT"))
if sid_REL_HP10:
    _counts["streams"] += 1
    _stream_ids["REL_HP10"] = sid_REL_HP10
else: _errors.append(("stream", "HandiPulse HP10 Release", "mk_stream returned None"))
if _project_ids.get("BFMSYS") and sid_REL_HP10:
    mk_stream_project(sid_REL_HP10, _project_ids["BFMSYS"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("BFMPERF") and sid_REL_HP10:
    mk_stream_project(sid_REL_HP10, _project_ids["BFMPERF"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("TXDSYS") and sid_REL_HP10:
    mk_stream_project(sid_REL_HP10, _project_ids["TXDSYS"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("TXDPERF") and sid_REL_HP10:
    mk_stream_project(sid_REL_HP10, _project_ids["TXDPERF"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("IMGSYS") and sid_REL_HP10:
    mk_stream_project(sid_REL_HP10, _project_ids["IMGSYS"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1
if _project_ids.get("IMGPERF") and sid_REL_HP10:
    mk_stream_project(sid_REL_HP10, _project_ids["IMGPERF"], INITIAL_STREAM_ID)
    _counts["stream_project_links"] += 1

# ─── Summary & Validation ────────────────────────────────────────────────
print("\n" + "=" * 58)
print("EXECUTION SUMMARY")
print("=" * 58)
expected = {"streams": 10, "projects": 6, "trackers": 12, "requirements": 12, "test_cases": 12, "verifies": 12, "stream_project_links": 48}
rows = [
    ("Streams",      _counts["streams"],      expected["streams"]),
    ("Projects",     _counts["projects"],     expected["projects"]),
    ("Trackers",     _counts["trackers"],     expected["trackers"]),
    ("Requirements", _counts["requirements"], expected["requirements"]),
    ("Test Cases",   _counts["test_cases"],   expected["test_cases"]),
    ("Verifies",     _counts["verifies"],     expected["verifies"]),
    ("Stream-Proj",  _counts["stream_project_links"], expected["stream_project_links"]),
]
print(f"  {'Category':<16} {'Actual':>8} {'Expected':>10}  Status")
print(f"  {'-'*16} {'-'*8} {'-'*10}  {'-'*6}")
all_ok = True
for label, actual, exp in rows:
    status = "OK" if actual >= exp else "MISSING"
    if actual < exp: all_ok = False
    flag = "  " if actual >= exp else "!!"
    print(f"  {flag} {label:<14} {actual:>8} {exp:>10}  {status}")
print()
if _errors:
    print(f"ERRORS ({len(_errors)}):")
    for cat, name, msg in _errors:
        print(f"  [{cat.upper()}] {name}: {msg}")
    print()
if all_ok and not _errors:
    print("All items created successfully.")
elif DRY_RUN:
    print("Dry-run complete — no API calls were made.")
else:
    print("Some items failed — review errors above.")
print()
print("Next steps in CB UI:")
print("  1. ALM > Streams: verify hierarchy Library -> PL -> Transform -> Release")
print("  2. Click a Library stream — you should see its branched projects")
print("  3. Edit a requirement in Library stream, then check PL — they are independent")
print("  4. Demo merge workflow: propagate changes between streams")