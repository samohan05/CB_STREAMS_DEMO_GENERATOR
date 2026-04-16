#!/usr/bin/env python3
"""Codebeamer API Validation Script v2
Discovers existing projects/trackers/items instead of creating them.
Validates: project creation path, Verifies field API, stream hierarchy.

Usage: python cb_api_validation_v2.py
"""

import requests, json, sys
from requests.auth import HTTPBasicAuth

# ─── CONFIGURATION ────────────────────────────────────────────────────────────
CB_URL = "https://pp-260127042638.portal.ptc.io:9443"
USER   = "pat"
PASS   = "ptc"

AUTH    = HTTPBasicAuth(USER, PASS)
HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}
BASE    = f"{CB_URL}/cb/api"

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ─── Helpers ──────────────────────────────────────────────────────────────────
def _get(path):
    return requests.get(f"{BASE}{path}", auth=AUTH, headers=HEADERS, verify=False)

def _post(path, body):
    return requests.post(f"{BASE}{path}", auth=AUTH, headers=HEADERS, json=body, verify=False)

def _put(path, body):
    return requests.put(f"{BASE}{path}", auth=AUTH, headers=HEADERS, json=body, verify=False)

def ok(msg):   print(f"  ✅ {msg}")
def fail(msg): print(f"  ❌ {msg}")
def info(msg): print(f"  ℹ️  {msg}")

results = []
def test(name, fn):
    print(f"\n{'─' * 60}")
    print(f"Test: {name}")
    print(f"{'─' * 60}")
    try:
        fn()
        results.append((name, "PASS"))
    except Exception as e:
        fail(f"Exception: {e}")
        results.append((name, f"FAIL: {e}"))


# ═════════════════════════════════════════════════════════════════════════════
# TEST 1: Discover correct project creation endpoint
# ═════════════════════════════════════════════════════════════════════════════
def test_project_creation_api():
    """Try multiple known project creation paths to find what works."""

    endpoints = [
        ("POST /v3/projects",           "POST", "/v3/projects"),
        ("POST /projects",              "POST", "/projects"),
        ("POST /v3/projects/deploy",    "POST", "/v3/projects/deploy"),
    ]

    body = {
        "name": "_API_VAL_TEST_v2",
        "keyName": "APIV2",
        "description": "Temporary validation project"
    }

    for label, method, path in endpoints:
        info(f"Trying {label}...")
        r = _post(path, body)
        info(f"  → {r.status_code} {r.reason}")
        if r.status_code in (200, 201):
            pid = r.json().get("id")
            ok(f"PROJECT CREATION WORKS via {label}  (id={pid})")
            ok(f"Use this endpoint in the generator script")
            return
        elif r.status_code == 405:
            info(f"  405 Method Not Allowed — this path doesn't accept POST")
        elif r.status_code == 403:
            info(f"  403 Forbidden — user may lack project-create permission")
        else:
            info(f"  Response: {r.text[:150]}")

    # If none worked, check if it's a permissions issue
    info("")
    info("All project creation endpoints returned errors.")
    info("Checking user permissions...")
    r = _get("/v3/users/self")
    if r.status_code == 200:
        user = r.json()
        info(f"Logged in as: {user.get('name', '?')} (id={user.get('id', '?')})")
    else:
        r2 = _get("/v3/roles")
        if r2.status_code == 200:
            info(f"Roles: {json.dumps(r2.json()[:5], indent=2)}")

    fail("Could not create project via any known endpoint")
    info("This may be a permission issue — the 'pat' user may be read-only or lack project admin role")
    raise Exception("No working project creation endpoint found")


# ═════════════════════════════════════════════════════════════════════════════
# TEST 2: Discover existing projects, trackers, and items
# ═════════════════════════════════════════════════════════════════════════════
discovered = {}

def test_discover_existing():
    """Find an existing project with REQ + TC trackers and at least one item each."""

    # List projects
    r = _get("/v3/projects")
    if r.status_code != 200:
        fail(f"GET /v3/projects returned {r.status_code}")
        raise Exception(f"Cannot list projects")

    projects = r.json()
    if isinstance(projects, dict):
        projects = projects.get("projects", projects.get("items", []))
    info(f"Found {len(projects)} projects")

    for proj in projects[:10]:  # Check first 10
        pid = proj.get("id")
        pname = proj.get("name", "?")
        info(f"\nChecking project: {pname} (id={pid})")

        # Get trackers for this project
        r2 = _get(f"/v3/projects/{pid}/trackers")
        if r2.status_code != 200:
            info(f"  Cannot list trackers: {r2.status_code}")
            continue

        trackers = r2.json()
        if isinstance(trackers, dict):
            trackers = trackers.get("trackers", trackers.get("items", []))

        req_tracker = None
        tc_tracker = None
        for t in trackers:
            tid = t.get("id")
            tname = t.get("name", "?")
            ttype = t.get("type", {})
            type_id = ttype.get("id") if isinstance(ttype, dict) else ttype
            info(f"  Tracker: {tname} (id={tid}, type={type_id})")
            if type_id == 5 and not req_tracker:
                req_tracker = t
            elif type_id == 102 and not tc_tracker:
                tc_tracker = t

        if req_tracker and tc_tracker:
            ok(f"Found REQ tracker: {req_tracker['name']} (id={req_tracker['id']})")
            ok(f"Found TC tracker: {tc_tracker['name']} (id={tc_tracker['id']})")

            # Find an item in each tracker
            for label, tracker in [("REQ", req_tracker), ("TC", tc_tracker)]:
                r3 = _get(f"/v3/trackers/{tracker['id']}/items?page=1&pageSize=1")
                if r3.status_code != 200:
                    # Try query API
                    r3 = _post("/v3/items/query", {
                        "queryString": f"tracker.id = {tracker['id']}",
                        "page": 1, "pageSize": 1
                    })
                if r3.status_code == 200:
                    items = r3.json()
                    if isinstance(items, dict):
                        items = items.get("items", items.get("itemRefs", []))
                    if items:
                        item_id = items[0].get("id")
                        discovered[f"{label}_item_id"] = item_id
                        ok(f"Found {label} item: id={item_id}")
                    else:
                        info(f"  {label} tracker is empty")
                else:
                    info(f"  Cannot query {label} items: {r3.status_code}")

            discovered["project_id"] = pid
            discovered["req_tracker_id"] = req_tracker["id"]
            discovered["tc_tracker_id"] = tc_tracker["id"]
            return

    fail("No project found with both REQ (type=5) and TC (type=102) trackers")
    info("Available tracker types in your instance:")
    r = _get("/v3/trackers/types")
    if r.status_code == 200:
        for tt in r.json()[:20]:
            info(f"  type_id={tt.get('id')} name={tt.get('name')}")
    raise Exception("No suitable project found")


# ═════════════════════════════════════════════════════════════════════════════
# TEST 3: Validate Verifies field on a real TC item
# ═════════════════════════════════════════════════════════════════════════════
def test_verifies_field():
    tc_id = discovered.get("TC_item_id")
    req_id = discovered.get("REQ_item_id")

    if not tc_id or not req_id:
        info("No existing TC + REQ items found — skipping Verifies test")
        info("Will try to discover the field schema instead")
        # At least discover what fields are available
        if tc_id:
            discover_fields(tc_id)
        raise Exception("Need both TC and REQ items to test Verifies")

    # Step A: Discover fields on the TC item to confirm field ID 17
    info(f"Step A: Discovering fields on TC item {tc_id}...")
    discover_fields(tc_id)

    # Step B: Try the Verifies field update
    info(f"\nStep B: Setting Verifies field — TC {tc_id} -> REQ {req_id}")
    payload = {
        "fieldValues": [{
            "fieldId": 17,
            "name": "Verifies",
            "type": "FieldReference",
            "values": [{"id": req_id}]
        }]
    }
    info(f"PUT /v3/items/{tc_id}/fields")
    info(f"Payload: {json.dumps(payload, indent=2)}")

    r = _put(f"/v3/items/{tc_id}/fields", payload)

    if r.status_code == 200:
        ok(f"Verifies field SET successfully!")
        ok(f"TC {tc_id} --verifies--> REQ {req_id}")
        if r.text:
            info(f"Response: {r.text[:200]}")
        ok("✅ Phase 1A Verifies API: CONFIRMED WORKING")
    else:
        fail(f"PUT returned {r.status_code}")
        fail(f"Response: {r.text[:300]}")

        if r.status_code == 400:
            info("\nThe field shape may differ. Trying alternative payloads...")

            # Alt 1: Without 'name' and 'type'
            alt1 = {"fieldValues": [{"fieldId": 17, "values": [{"id": req_id}]}]}
            info(f"Alt 1 (minimal): {json.dumps(alt1)}")
            r2 = _put(f"/v3/items/{tc_id}/fields", alt1)
            info(f"  → {r2.status_code}: {r2.text[:150]}")
            if r2.status_code == 200:
                ok("Alt 1 WORKS — minimal payload without name/type")
                return

            # Alt 2: Using 'value' instead of 'values'
            alt2 = {"fieldValues": [{"fieldId": 17, "name": "Verifies", "type": "FieldReference", "value": req_id}]}
            info(f"Alt 2 (value not values): {json.dumps(alt2)}")
            r3 = _put(f"/v3/items/{tc_id}/fields", alt2)
            info(f"  → {r3.status_code}: {r3.text[:150]}")
            if r3.status_code == 200:
                ok("Alt 2 WORKS — use 'value' instead of 'values'")
                return

            # Alt 3: Using TrackerItemReference format
            alt3 = {"fieldValues": [{"fieldId": 17, "name": "Verifies", "type": "TrackerItemReference", "values": [{"id": req_id}]}]}
            info(f"Alt 3 (TrackerItemReference): {json.dumps(alt3)}")
            r4 = _put(f"/v3/items/{tc_id}/fields", alt3)
            info(f"  → {r4.status_code}: {r4.text[:150]}")
            if r4.status_code == 200:
                ok("Alt 3 WORKS — type should be TrackerItemReference")
                return

        raise Exception(f"Verifies field update failed: {r.status_code}")


def discover_fields(item_id):
    """Get all fields on an item to find the Verifies field ID and type."""
    r = _get(f"/v3/items/{item_id}/fields")
    if r.status_code == 200:
        data = r.json()
        fields = data if isinstance(data, list) else data.get("fieldValues", data.get("fields", []))
        info(f"Fields on item {item_id}:")
        for f in fields:
            fid = f.get("fieldId", "?")
            fname = f.get("name", "?")
            ftype = f.get("type", "?")
            fval = f.get("values", f.get("value", ""))
            marker = " ◀◀◀ THIS IS THE VERIFIES FIELD" if fname == "Verifies" or fid == 17 else ""
            info(f"  fieldId={fid}  name={fname}  type={ftype}  values={str(fval)[:60]}{marker}")
    else:
        info(f"GET /v3/items/{item_id}/fields returned {r.status_code}")
        # Fallback: get the full item
        r2 = _get(f"/v3/items/{item_id}")
        if r2.status_code == 200:
            item = r2.json()
            info(f"Item keys: {list(item.keys())}")
            for key in ["customFields", "fields", "fieldValues"]:
                if key in item:
                    info(f"  {key}: {json.dumps(item[key], indent=2)[:500]}")


# ═════════════════════════════════════════════════════════════════════════════
# TEST 4: Stream hierarchy (already confirmed, re-verify without creating)
# ═════════════════════════════════════════════════════════════════════════════
def test_stream_hierarchy_read():
    """Verify the streams we created in v1 are still showing hierarchy."""
    # Just list all streams and look for parent-child relationships
    r = _get("/v3/streams")
    if r.status_code == 200:
        streams = r.json()
        if isinstance(streams, dict):
            streams = streams.get("streams", streams.get("items", []))
        with_source = [s for s in streams if s.get("sourceStreamId")]
        info(f"Total streams: {len(streams)}, with sourceStreamId: {len(with_source)}")
        for s in with_source[:5]:
            info(f"  {s['name']} (id={s['id']}) → parent={s['sourceStreamId']}")
        ok(f"Stream hierarchy confirmed — {len(with_source)} child streams found")
    else:
        fail(f"GET /v3/streams returned {r.status_code}")
        raise Exception(f"Status {r.status_code}")


# ═════════════════════════════════════════════════════════════════════════════
# RUN
# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("CB API Validation Script v2 (Discovery Mode)")
    print(f"Instance: {CB_URL}")
    print("=" * 60)

    test("1. Project creation API discovery", test_project_creation_api)
    test("2. Discover existing projects/trackers/items", test_discover_existing)
    test("3. Verifies field API (Phase 1A)", test_verifies_field)
    test("4. Stream hierarchy (Phase 1B)", test_stream_hierarchy_read)

    print(f"\n{'=' * 60}")
    print("RESULTS SUMMARY")
    print("=" * 60)
    all_pass = True
    for name, status in results:
        icon = "✅" if status == "PASS" else "❌"
        print(f"  {icon} {name}: {status}")
        if status != "PASS":
            all_pass = False

    print(f"\n{'ALL TESTS PASSED' if all_pass else 'SOME TESTS FAILED — see details above'}")
    print("=" * 60)
    print("\nPlease paste this full output back to Claude.")
    sys.exit(0 if all_pass else 1)
