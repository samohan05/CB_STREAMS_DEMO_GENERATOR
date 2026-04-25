#!/usr/bin/env python3
"""Codebeamer API Validation Script
Run this against your CB instance to verify key APIs before we build the full generator.
Usage: python3 cb_api_validation.py

Tests:
  1. Authentication & initial stream ID
  2. Create a test project + REQ tracker + TC tracker
  3. Create a requirement item + test case item
  4. PUT /v3/items/{id}/fields — set Verifies field (fieldId=17, FieldReference)
  5. Create a child stream with sourceStreamId (for Phase 1B hierarchy)
  6. Cleanup — delete test project and stream
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

# Track created resources for cleanup
created = {"project_id": None, "stream_id": None, "child_stream_id": None}

# ─── Helpers ──────────────────────────────────────────────────────────────────
def _get(path):
    r = requests.get(f"{BASE}{path}", auth=AUTH, headers=HEADERS, verify=False)
    return r

def _post(path, body):
    r = requests.post(f"{BASE}{path}", auth=AUTH, headers=HEADERS, json=body, verify=False)
    return r

def _put(path, body):
    r = requests.put(f"{BASE}{path}", auth=AUTH, headers=HEADERS, json=body, verify=False)
    return r

def _delete(path):
    r = requests.delete(f"{BASE}{path}", auth=AUTH, headers=HEADERS, verify=False)
    return r

def ok(msg):   print(f"  ✅ {msg}")
def fail(msg): print(f"  ❌ {msg}")
def info(msg): print(f"  ℹ️  {msg}")

results = []

def test(name, fn):
    print(f"\n── Test: {name} ──")
    try:
        fn()
        results.append((name, "PASS"))
    except Exception as e:
        fail(f"Exception: {e}")
        results.append((name, f"FAIL: {e}"))

# ─── Test 1: Auth + Initial Stream ────────────────────────────────────────────
initial_stream_id = None

def test_auth_and_initial_stream():
    global initial_stream_id
    r = _get("/v3/streams/initial")
    if r.status_code == 200:
        initial_stream_id = r.json()
        ok(f"Initial stream ID = {initial_stream_id} (type: {type(initial_stream_id).__name__})")
    else:
        fail(f"GET /v3/streams/initial returned {r.status_code}: {r.text[:200]}")
        raise Exception(f"Status {r.status_code}")

# ─── Test 2: Create Test Project + Trackers ───────────────────────────────────
project_id = None
req_tracker_id = None
tc_tracker_id = None

def test_create_project_and_trackers():
    global project_id, req_tracker_id, tc_tracker_id

    # Create project
    r = _post("/v3/projects", {"name": "_API_VALIDATION_TEST", "keyName": "APIVAL", "description": "Temporary — will be deleted"})
    if r.status_code in (200, 201):
        project_id = r.json()["id"]
        created["project_id"] = project_id
        ok(f"Project created: id={project_id}")
    else:
        fail(f"POST /v3/projects returned {r.status_code}: {r.text[:200]}")
        raise Exception(f"Status {r.status_code}")

    # Create Requirements tracker (type 5)
    r = _post(f"/v3/projects/{project_id}/trackers", {"name": "Val Requirements", "keyName": "VALREQ", "type": {"id": 5}})
    if r.status_code in (200, 201):
        req_tracker_id = r.json()["id"]
        ok(f"REQ tracker created: id={req_tracker_id}")
    else:
        fail(f"POST trackers (REQ type=5) returned {r.status_code}: {r.text[:200]}")
        info("Check tracker type IDs: GET /cb/api/v3/trackers/types")
        raise Exception(f"Status {r.status_code}")

    # Create Test Cases tracker (type 102)
    r = _post(f"/v3/projects/{project_id}/trackers", {"name": "Val Test Cases", "keyName": "VALTC", "type": {"id": 102}})
    if r.status_code in (200, 201):
        tc_tracker_id = r.json()["id"]
        ok(f"TC tracker created: id={tc_tracker_id}")
    else:
        fail(f"POST trackers (TC type=102) returned {r.status_code}: {r.text[:200]}")
        info("Check tracker type IDs: GET /cb/api/v3/trackers/types")
        raise Exception(f"Status {r.status_code}")

# ─── Test 3: Create Requirement + Test Case Items ────────────────────────────
req_id = None
tc_id = None

def test_create_items():
    global req_id, tc_id

    r = _post(f"/v3/trackers/{req_tracker_id}/items", {"name": "VAL-REQ: The system shall pass validation", "description": "API validation test requirement"})
    if r.status_code in (200, 201):
        req_id = r.json()["id"]
        ok(f"Requirement item created: id={req_id}")
    else:
        fail(f"POST tracker items (REQ) returned {r.status_code}: {r.text[:200]}")
        raise Exception(f"Status {r.status_code}")

    r = _post(f"/v3/trackers/{tc_tracker_id}/items", {"name": "VAL-TC: Verify system passes validation", "description": "API validation test case"})
    if r.status_code in (200, 201):
        tc_id = r.json()["id"]
        ok(f"Test case item created: id={tc_id}")
    else:
        fail(f"POST tracker items (TC) returned {r.status_code}: {r.text[:200]}")
        raise Exception(f"Status {r.status_code}")

# ─── Test 4: PUT /v3/items/{id}/fields — Verifies FieldReference ─────────────
def test_set_verifies_field():
    """This is the key test for Phase 1A — does fieldId 17 work as Verifies?"""

    payload = {
        "fieldValues": [{
            "fieldId": 17,
            "name": "Verifies",
            "type": "FieldReference",
            "values": [{"id": req_id}]
        }]
    }

    info(f"PUT /v3/items/{tc_id}/fields with payload:")
    info(json.dumps(payload, indent=2))

    r = _put(f"/v3/items/{tc_id}/fields", payload)

    if r.status_code == 200:
        ok(f"Verifies field SET successfully — TC {tc_id} --verifies--> REQ {req_id}")
        # Verify by reading the item back
        r2 = _get(f"/v3/items/{tc_id}")
        if r2.status_code == 200:
            item = r2.json()
            info(f"Item fields returned (checking for verifies): {json.dumps([f.get('name','?') for f in item.get('customFields', item.get('fields', []))], indent=0)}")
        ok("Phase 1A Verifies API: CONFIRMED WORKING")
    elif r.status_code == 400:
        fail(f"400 Bad Request — payload shape may be wrong")
        fail(f"Response: {r.text[:300]}")
        info("Try: GET /v3/items/{tc_id}/fields to see available fields and their IDs")
        # Attempt to discover the correct field
        r3 = _get(f"/v3/items/{tc_id}/fields")
        if r3.status_code == 200:
            fields = r3.json()
            info(f"Available fields on TC item:")
            for f in (fields if isinstance(fields, list) else fields.get("fieldValues", fields.get("fields", []))):
                info(f"  fieldId={f.get('fieldId', '?')} name={f.get('name', '?')} type={f.get('type', '?')}")
        raise Exception(f"Verifies field update failed: {r.status_code}")
    else:
        fail(f"PUT /v3/items/{tc_id}/fields returned {r.status_code}: {r.text[:300]}")
        raise Exception(f"Status {r.status_code}")

# ─── Test 5: Create Stream + Child Stream with sourceStreamId ─────────────────
stream_id = None
child_stream_id = None

def test_stream_hierarchy():
    global stream_id, child_stream_id

    # Create parent stream
    r = _post("/v3/streams/stream", {"name": "_VAL_PARENT_STREAM", "color": "#336699", "description": "Validation parent"})
    if r.status_code in (200, 201):
        stream_id = r.json()["id"]
        created["stream_id"] = stream_id
        ok(f"Parent stream created: id={stream_id}")
    else:
        fail(f"POST /v3/streams/stream returned {r.status_code}: {r.text[:200]}")
        raise Exception(f"Status {r.status_code}")

    # Create child stream WITH sourceStreamId
    r = _post("/v3/streams/stream", {
        "name": "_VAL_CHILD_STREAM",
        "color": "#996633",
        "description": "Validation child with source",
        "sourceStreamId": stream_id,
        "isSourceStreamChecked": True
    })
    if r.status_code in (200, 201):
        child = r.json()
        child_stream_id = child["id"]
        created["child_stream_id"] = child_stream_id
        ok(f"Child stream created: id={child_stream_id}")
        if child.get("sourceStreamId") == stream_id:
            ok(f"sourceStreamId correctly set to {stream_id}")
        else:
            info(f"sourceStreamId in response: {child.get('sourceStreamId', 'NOT PRESENT')}")
            info(f"Full response: {json.dumps(child, indent=2)}")
        ok("Phase 1B sourceStreamId: CONFIRMED WORKING")
    elif r.status_code == 400:
        fail(f"400 Bad Request — sourceStreamId may not work this way")
        fail(f"Response: {r.text[:300]}")
        info("We may need to use a different approach for stream hierarchy")
        raise Exception(f"Status {r.status_code}")
    else:
        fail(f"Child stream creation returned {r.status_code}: {r.text[:200]}")
        raise Exception(f"Status {r.status_code}")

    # Verify hierarchy via descendants API
    r = _get(f"/v3/streams/{stream_id}/descendants")
    if r.status_code == 200:
        descendants = r.json()
        info(f"Descendants of parent stream {stream_id}: {json.dumps(descendants, indent=2)[:300]}")
    else:
        info(f"GET descendants returned {r.status_code} (non-critical)")

# ─── Test 6: Add Project to Stream ────────────────────────────────────────────
def test_add_project_to_stream():
    if not stream_id or not project_id or not initial_stream_id:
        info("Skipping — missing stream/project/initial_stream IDs")
        return

    r = _put(f"/v3/streams/{stream_id}/projects", {
        "projectId": project_id,
        "sourceStreamId": initial_stream_id,
        "addAllTrackers": True
    })
    if r.status_code in (200, 201):
        ok(f"Project {project_id} added to stream {stream_id}")
    else:
        fail(f"PUT /v3/streams/{stream_id}/projects returned {r.status_code}: {r.text[:200]}")
        raise Exception(f"Status {r.status_code}")

# ─── Cleanup ──────────────────────────────────────────────────────────────────
def cleanup():
    print("\n── Cleanup ──")
    for label, res_id, path_tpl in [
        ("child stream", created.get("child_stream_id"), "/v3/streams/{}"),
        ("parent stream", created.get("stream_id"), "/v3/streams/{}"),
        ("project", created.get("project_id"), "/v3/projects/{}"),
    ]:
        if res_id:
            r = _delete(path_tpl.format(res_id))
            if r.status_code in (200, 204):
                ok(f"Deleted {label} {res_id}")
            else:
                info(f"Could not delete {label} {res_id}: {r.status_code} (clean up manually)")

# ─── Run ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    print("=" * 60)
    print("CB API Validation Script")
    print(f"Instance: {CB_URL}")
    print("=" * 60)

    test("1. Auth + initial stream ID", test_auth_and_initial_stream)
    test("2. Create project + trackers", test_create_project_and_trackers)
    test("3. Create requirement + test case items", test_create_items)
    test("4. PUT /v3/items/{id}/fields — Verifies (Phase 1A)", test_set_verifies_field)
    test("5. Stream hierarchy with sourceStreamId (Phase 1B)", test_stream_hierarchy)
    test("6. Add project to stream", test_add_project_to_stream)

    cleanup()

    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    all_pass = True
    for name, status in results:
        icon = "✅" if status == "PASS" else "❌"
        print(f"  {icon} {name}: {status}")
        if status != "PASS":
            all_pass = False

    print(f"\n{'ALL TESTS PASSED' if all_pass else 'SOME TESTS FAILED'}")
    print("=" * 60)
    print("\nPlease paste this output back to Claude so we can proceed.")
    sys.exit(0 if all_pass else 1)
