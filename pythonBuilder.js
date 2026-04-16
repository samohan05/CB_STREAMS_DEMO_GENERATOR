// ─── pythonBuilder.js ────────────────────────────────────────────────────────
// Generates a complete Python provisioning script from a DemoStructure.
// v3: Explicit parent_stream_key derivation. PL aggregates from multiple libraries.
//     Phase 1: create all projects. Phase 2: create streams with explicit parents.

import { TIERS, TIER_LABELS } from './templates.js';
import { esc, safeV, countAll } from './helpers.js';

/**
 * @typedef {import('./helpers.js').DemoStructure} DemoStructure
 */

const i1 = t => "    " + t;
const i2 = t => "        " + t;

/**
 * Build the static Python header.
 * @param {DemoStructure} s
 * @param {string} url
 * @param {string} user
 * @returns {string}
 */
function buildPythonHeader(s, url, user) {
  return `#!/usr/bin/env python3
"""Codebeamer Demo Generator
Domain   : ${esc(s.domain_name)}
Generated: ${new Date().toISOString().split("T")[0]}

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

CB_URL = os.environ.get("CB_URL",  "") or "${esc(url || "https://your-cb-instance.com")}"
USER   = os.environ.get("CB_USER", "") or "${esc(user || "")}"
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
            if not r.ok:
                # Include server response body in error for diagnostics
                detail = ""
                try: detail = f" | Server response: {r.text[:500]}"
                except Exception: pass
                raise requests.HTTPError(
                    f"{r.status_code} {r.reason} for {method.upper()} {path}{detail}",
                    response=r)
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
            if not r.ok:
                detail = ""
                try: detail = f" | Server response: {r.text[:500]}"
                except Exception: pass
                raise requests.HTTPError(
                    f"{r.status_code} {r.reason} for {method.upper()} {path}{detail}",
                    response=r)
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
        warn(f"  [STREAM-PROJ] p{project_id}->s{stream_id}: {e}")`;
}


// ─── Python script body ─────────────────────────────────────────────────────

/**
 * Build the dynamic body: Phase 1 (projects) + Phase 2 (streams with explicit parents).
 * @param {DemoStructure} s
 * @returns {string[]}
 */
function buildPythonBody(s) {
  const L = [];
  const ln = t => L.push(t);

  ln(`print("=" * 58)`);
  ln(`print(f"CB Demo: ${esc(s.domain_name)}")`);
  ln(`if DRY_RUN: print("  ** DRY-RUN MODE — no API calls will be made **")`);
  ln(`if CLEAN:   print("  ** CLEAN MODE — existing projects will be deleted first **")`);
  ln(`print("=" * 58)`);
  ln(``);

  // ── Initial stream fetch ──
  ln(`if not DRY_RUN:`);
  ln(i1(`print("\\n[INIT] Fetching initial stream ID...")`));
  ln(i1(`try:`));
  ln(i2(`INITIAL_STREAM_ID = _get("/v3/streams/initial")`));
  ln(i2(`if isinstance(INITIAL_STREAM_ID, dict):`));
  ln(i2(`    INITIAL_STREAM_ID = INITIAL_STREAM_ID.get("id", INITIAL_STREAM_ID)`));
  ln(i2(`ok(f"Initial stream ID = {INITIAL_STREAM_ID}")`));
  ln(i1(`except Exception as e:`));
  ln(i2(`warn(f"Cannot fetch initial stream ID: {e}")`));
  ln(i2(`sys.exit(1)`));
  ln(`else:`);
  ln(i1(`INITIAL_STREAM_ID = None`));
  ln(i1(`ok("[DRY-RUN] Skipping initial stream fetch")`));
  ln(``);

  // ── Auto-discovery ──
  ln(`# ─── Auto-discover tracker type IDs and Verifies field ID ──────────────`);
  ln(`if not DRY_RUN:`);
  ln(i1(`print("\\n[DISCOVER] Auto-detecting tracker types and field IDs...")`));
  ln(i1(`_req_type, _tc_type = discover_tracker_types()`));
  ln(i1(`if _req_type: REQ_TYPE_ID = _req_type`));
  ln(i1(`if _tc_type:  TC_TYPE_ID  = _tc_type`));
  ln(i1(`if not _req_type or not _tc_type:`));
  ln(i2(`warn(f"Using defaults: REQ_TYPE_ID={REQ_TYPE_ID}, TC_TYPE_ID={TC_TYPE_ID}")`));
  ln(`else:`);
  ln(i1(`ok("[DRY-RUN] Skipping auto-discovery, using defaults")`));
  ln(``);
  ln(`_verifies_discovered = False`);
  ln(``);
  ln(`# ─── Execution tracking ────────────────────────────────────────────────`);
  ln(`_counts = {"streams": 0, "projects": 0, "trackers": 0, "requirements": 0, "test_cases": 0, "verifies": 0, "stream_project_links": 0}`);
  ln(`_errors = []`);
  ln(``);
  ln(`# Project key -> CB project ID mapping (Phase 1 populates, Phase 2 uses)`);
  ln(`_project_ids = {}`);
  ln(``);
  ln(`# Stream key -> CB stream ID mapping (for parent_stream_key resolution)`);
  ln(`_stream_ids = {}`);
  ln(``);

  // ════════════════════════════════════════════════════════════════════════
  // PHASE 1: Create all projects
  // ════════════════════════════════════════════════════════════════════════
  ln(`# ${"═".repeat(70)}`);
  ln(`# PHASE 1: Create all projects (in Initial Stream)`);
  ln(`# ${"═".repeat(70)}`);
  ln(`print("\\n" + "=" * 58)`);
  ln(`print("PHASE 1: Creating Projects, Trackers, Requirements, Test Cases")`);
  ln(`print("=" * 58)`);
  ln(``);

  const projects = s.projects || [];
  projects.forEach((p, pi) => {
    const pKey = (p.project_key || "KEY").substring(0, 8);
    const pv   = `pid_${safeV(p.project_key || `p${pi}`)}`;
    const rtv  = `rtid_${pv}`;
    const ttv  = `ttid_${pv}`;

    ln(`# ── Project: ${esc(p.project_name)} ──`);
    ln(`${pv} = mk_project("${esc(p.project_name)}", "${esc(pKey)}", "${esc(p.description || '')}")`);
    ln(`if ${pv}:`);
    ln(i1(`_counts["projects"] += 1`));
    ln(i1(`_project_ids["${esc(pKey)}"] = ${pv}`));
    ln(`else: _errors.append(("project", "${esc(p.project_name)}", "mk_project returned None"))`);
    ln(`${rtv} = mk_tracker(${pv}, "Requirements", "REQ", REQ_TYPE_ID)`);
    ln(`if ${rtv}: _counts["trackers"] += 1`);
    ln(`else: _errors.append(("tracker", "Requirements for ${esc(p.project_name)}", "mk_tracker returned None"))`);
    ln(`${ttv} = mk_tracker(${pv}, "Test Cases", "TC", TC_TYPE_ID)`);
    ln(`if ${ttv}: _counts["trackers"] += 1`);
    ln(`else: _errors.append(("tracker", "Test Cases for ${esc(p.project_name)}", "mk_tracker returned None"))`);
    ln(`if not _verifies_discovered and ${ttv} and not DRY_RUN:`);
    ln(i1(`_vf = discover_verifies_field(${ttv}, ${pv})`));
    ln(i1(`if _vf: VERIFIES_FIELD_ID = _vf`));
    ln(i1(`else: warn(f"Using default VERIFIES_FIELD_ID={VERIFIES_FIELD_ID}")`));
    ln(i1(`_verifies_discovered = True`));

    (p.requirements || []).forEach((req, ri) => {
      const rv = `rid_${pv}_${ri}`;
      ln(`${rv} = mk_item(${rtv}, "${esc(req.title)}", "${esc(req.description)}")`);
      ln(`if ${rv}: _counts["requirements"] += 1`);
      ln(`else: _errors.append(("requirement", "${esc(req.title).substring(0, 60)}", "mk_item returned None"))`);
      (req.test_cases || []).forEach((tc, tci) => {
        const tcv = `tcid_${pv}_${ri}_${tci}`;
        const d = `${esc(tc.description)} Steps: ${esc(tc.steps)} Expected: ${esc(tc.expected_result)}`.substring(0, 350);
        ln(`if ${rv}:`);
        ln(i1(`${tcv} = mk_item(${ttv}, "${esc(tc.title)}", "${d}")`));
        ln(i1(`if ${tcv}: _counts["test_cases"] += 1`));
        ln(i1(`if set_verifies(${tcv}, ${rv}): _counts["verifies"] += 1`));
      });
    });
    ln(``);
  });

  // ════════════════════════════════════════════════════════════════════════
  // PHASE 2: Create streams with explicit parent derivation + add projects
  // ════════════════════════════════════════════════════════════════════════
  ln(`# ${"═".repeat(70)}`);
  ln(`# PHASE 2: Create Stream Hierarchy & Add Projects to Streams`);
  ln(`# Library (top) -> PL (top) -> Transform (parent=PL) -> Release (parent=Transform)`);
  ln(`# ${"═".repeat(70)}`);
  ln(`print("\\n" + "=" * 58)`);
  ln(`print("PHASE 2: Creating Streams & Adding Projects")`);
  ln(`print("=" * 58)`);
  ln(``);

  TIERS.forEach((tier) => {
    const streams = s[tier.key] || [];
    if (!streams.length) return;

    ln(`# -- ${TIER_LABELS[tier.key]} --`);
    ln(`print("\\n[${tier.short}] ${TIER_LABELS[tier.key]}")`);

    streams.forEach((st, si) => {
      const sv = `sid_${safeV(st.stream_key || `${tier.short}${si}`)}`;
      const parentKey = st.parent_stream_key;

      // Resolve parent: look up from _stream_ids dict, or None
      const parentExpr = parentKey
        ? `_stream_ids.get("${esc(parentKey)}")`
        : "None";

      ln(`${sv} = mk_stream("${esc(st.stream_name)}", "${esc(st.description)}", ${parentExpr})`);
      ln(`if ${sv}:`);
      ln(i1(`_counts["streams"] += 1`));
      ln(i1(`_stream_ids["${esc(st.stream_key)}"] = ${sv}`));
      ln(`else: _errors.append(("stream", "${esc(st.stream_name)}", "mk_stream returned None"))`);

      // Add referenced projects to this stream
      const projectKeys = st.project_keys || [];
      projectKeys.forEach(pk => {
        const pkEsc = esc(pk).substring(0, 8);
        ln(`if _project_ids.get("${pkEsc}") and ${sv}:`);
        ln(i1(`mk_stream_project(${sv}, _project_ids["${pkEsc}"], INITIAL_STREAM_ID)`));
        ln(i1(`_counts["stream_project_links"] += 1`));
      });
      ln(``);
    });
  });

  return L;
}


// ─── Summary ────────────────────────────────────────────────────────────────

/**
 * @param {DemoStructure} s
 * @returns {string[]}
 */
function buildPythonSummary(s) {
  const L = [];
  const ln = t => L.push(t);
  const expected = countAll(s);
  const expectedTrackers = expected.projects * 2;

  ln(`# ─── Summary & Validation ────────────────────────────────────────────────`);
  ln(`print("\\n" + "=" * 58)`);
  ln(`print("EXECUTION SUMMARY")`);
  ln(`print("=" * 58)`);
  ln(`expected = {"streams": ${expected.streams}, "projects": ${expected.projects}, "trackers": ${expectedTrackers}, "requirements": ${expected.reqs}, "test_cases": ${expected.tcs}, "verifies": ${expected.tcs}, "stream_project_links": ${expected.streamProjectLinks}}`);
  ln(`rows = [`);
  ln(`    ("Streams",      _counts["streams"],      expected["streams"]),`);
  ln(`    ("Projects",     _counts["projects"],     expected["projects"]),`);
  ln(`    ("Trackers",     _counts["trackers"],     expected["trackers"]),`);
  ln(`    ("Requirements", _counts["requirements"], expected["requirements"]),`);
  ln(`    ("Test Cases",   _counts["test_cases"],   expected["test_cases"]),`);
  ln(`    ("Verifies",     _counts["verifies"],     expected["verifies"]),`);
  ln(`    ("Stream-Proj",  _counts["stream_project_links"], expected["stream_project_links"]),`);
  ln(`]`);
  ln(`print(f"  {'Category':<16} {'Actual':>8} {'Expected':>10}  Status")`);
  ln(`print(f"  {'-'*16} {'-'*8} {'-'*10}  {'-'*6}")`);
  ln(`all_ok = True`);
  ln(`for label, actual, exp in rows:`);
  ln(i1(`status = "OK" if actual >= exp else "MISSING"`));
  ln(i1(`if actual < exp: all_ok = False`));
  ln(i1(`flag = "  " if actual >= exp else "!!"`));
  ln(i1(`print(f"  {flag} {label:<14} {actual:>8} {exp:>10}  {status}")`));
  ln(`print()`);
  ln(`if _errors:`);
  ln(i1(`print(f"ERRORS ({len(_errors)}):")`));
  ln(i1(`for cat, name, msg in _errors:`));
  ln(i2(`print(f"  [{cat.upper()}] {name}: {msg}")`));
  ln(i1(`print()`));
  ln(`if all_ok and not _errors:`);
  ln(i1(`print("All items created successfully.")`));
  ln(`elif DRY_RUN:`);
  ln(i1(`print("Dry-run complete — no API calls were made.")`));
  ln(`else:`);
  ln(i1(`print("Some items failed — review errors above.")`));
  ln(`print()`);
  ln(`print("Next steps in CB UI:")`);
  ln(`print("  1. ALM > Streams: verify hierarchy Library -> PL -> Transform -> Release")`);
  ln(`print("  2. Click a Library stream — you should see its branched projects")`);
  ln(`print("  3. Edit a requirement in Library stream, then check PL — they are independent")`);
  ln(`print("  4. Demo merge workflow: propagate changes between streams")`);

  return L;
}


// ─── Main export ─────────────────────────────────────────────────────────────

/**
 * @param {DemoStructure} s
 * @param {string}        url
 * @param {string}        user
 * @param {string}        pass_
 * @returns {string}
 */
export function buildPythonScript(s, url, user, pass_) {
  const header  = buildPythonHeader(s, url, user);
  const body    = buildPythonBody(s);
  const summary = buildPythonSummary(s);
  return [header, ...body, ...summary].join("\n");
}
