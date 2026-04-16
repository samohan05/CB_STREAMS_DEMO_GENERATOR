#!/usr/bin/env python3
"""Codebeamer API Validation Script v3 — Targeted
Uses known tracker IDs from discovery to test the Verifies field API.

Usage: python cb_api_validation_v3.py
"""

import requests, json, sys
from requests.auth import HTTPBasicAuth

CB_URL  = "https://pp-260127042638.portal.ptc.io:9443"
USER    = "pat"
PASS    = "ptc"
AUTH    = HTTPBasicAuth(USER, PASS)
HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}
BASE    = f"{CB_URL}/cb/api"

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 1: Find a requirement item and a test case item using cbQL
# ═══════════════════════════════════════════════════════════════════════════════
req_item_id = None
tc_item_id = None

def test_find_items():
    global req_item_id, tc_item_id

    # Strategy: query for items by tracker type using cbQL
    # type_id 5 = Requirement, type_id 102 = Testcase
    for type_name, type_id, label in [("Requirement", 5, "REQ"), ("Testcase", 102, "TC")]:
        info(f"Searching for a {label} item (tracker type {type_id})...")

        # Try cbQL query
        r = _post("/v3/items/query", {
            "queryString": f"tracker.type = '{type_name}'",
            "page": 1, "pageSize": 3
        })
        if r.status_code == 200:
            data = r.json()
            items = data.get("items", data.get("itemRefs", []))
            if items:
                item_id = items[0].get("id")
                item_name = items[0].get("name", "?")
                ok(f"Found {label}: id={item_id}  name={item_name[:60]}")
                if label == "REQ":
                    req_item_id = item_id
                else:
                    tc_item_id = item_id
                continue

        info(f"  cbQL by type name returned {r.status_code}: {r.text[:150]}")

        # Fallback: try numeric type query
        r2 = _post("/v3/items/query", {
            "queryString": f"tracker.typeId = {type_id}",
            "page": 1, "pageSize": 3
        })
        if r2.status_code == 200:
            data = r2.json()
            items = data.get("items", data.get("itemRefs", []))
            if items:
                item_id = items[0].get("id")
                ok(f"Found {label} via typeId: id={item_id}")
                if label == "REQ":
                    req_item_id = item_id
                else:
                    tc_item_id = item_id
                continue

        info(f"  cbQL by typeId returned {r2.status_code}: {r2.text[:150]}")

        # Fallback 2: Use known tracker IDs from v2 discovery
        # Medical Device Engineering Template trackers
        known_trackers = {
            "REQ": [9098, 9109, 9093, 9103],  # System Req, SW Req, User Req, Non-SW Req
            "TC":  [9086, 9094, 9095, 9096],   # Verification protocols
        }
        for tid in known_trackers.get(label, []):
            info(f"  Trying known tracker {tid}...")
            r3 = _post("/v3/items/query", {
                "queryString": f"tracker.id = {tid}",
                "page": 1, "pageSize": 1
            })
            if r3.status_code == 200:
                data = r3.json()
                items = data.get("items", data.get("itemRefs", []))
                if items:
                    item_id = items[0].get("id")
                    ok(f"Found {label} in tracker {tid}: id={item_id}")
                    if label == "REQ":
                        req_item_id = item_id
                    else:
                        tc_item_id = item_id
                    break

    if not req_item_id:
        fail("Could not find any requirement item")
    if not tc_item_id:
        fail("Could not find any test case item")
    if not req_item_id or not tc_item_id:
        raise Exception("Need both REQ and TC items")

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 2: Discover fields on the TC item
# ═══════════════════════════════════════════════════════════════════════════════
verifies_field_id = None
verifies_field_type = None

def test_discover_fields():
    global verifies_field_id, verifies_field_type

    info(f"Getting fields for TC item {tc_item_id}...")

    # Method A: GET /v3/items/{id}/fields
    r = _get(f"/v3/items/{tc_item_id}/fields")
    if r.status_code == 200:
        data = r.json()
        fields = data if isinstance(data, list) else data.get("fieldValues", data.get("fields", []))
        info(f"Found {len(fields)} fields via /fields endpoint:")
        for f in fields:
            fid = f.get("fieldId", "?")
            fname = f.get("name", "?")
            ftype = f.get("type", "?")
            is_verifies = "verif" in str(fname).lower()
            marker = " ◀◀◀ VERIFIES FIELD" if is_verifies else ""
            info(f"  fieldId={fid}  name={fname}  type={ftype}{marker}")
            if is_verifies:
                verifies_field_id = fid
                verifies_field_type = ftype
        if verifies_field_id:
            ok(f"Verifies field found: fieldId={verifies_field_id} type={verifies_field_type}")
            return
    else:
        info(f"  /fields returned {r.status_code}: {r.text[:150]}")

    # Method B: GET full item and inspect
    r2 = _get(f"/v3/items/{tc_item_id}")
    if r2.status_code == 200:
        item = r2.json()
        info(f"Full item keys: {list(item.keys())}")

        # Check customFields
        for key in ["customFields", "fields", "fieldValues"]:
            if key in item:
                fields = item[key]
                info(f"\n{key} ({len(fields)} entries):")
                for f in fields:
                    fid = f.get("fieldId", f.get("id", "?"))
                    fname = f.get("name", "?")
                    ftype = f.get("type", f.get("typeName", "?"))
                    is_verifies = "verif" in str(fname).lower()
                    marker = " ◀◀◀ VERIFIES FIELD" if is_verifies else ""
                    info(f"  id={fid}  name={fname}  type={ftype}{marker}")
                    if is_verifies:
                        verifies_field_id = fid
                        verifies_field_type = ftype

        # Also check for "Verifies" in the response text
        item_str = json.dumps(item)
        if "erif" in item_str.lower():
            # Find the context around "verif"
            idx = item_str.lower().find("erif")
            info(f"\n'verif' found in item JSON at position {idx}:")
            info(f"  ...{item_str[max(0,idx-80):idx+80]}...")
    else:
        info(f"GET item returned {r2.status_code}")

    if verifies_field_id:
        ok(f"Verifies field discovered: fieldId={verifies_field_id} type={verifies_field_type}")
    else:
        info("Verifies field not found in field list — it may only appear on trackers of type 102 (Testcase)")
        info("Will try fieldId=17 as specified in the Codebeamer docs")
        verifies_field_id = 17
        verifies_field_type = "FieldReference"

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 3: Set the Verifies field
# ═══════════════════════════════════════════════════════════════════════════════
def test_set_verifies():
    info(f"Setting Verifies: TC {tc_item_id} --verifies--> REQ {req_item_id}")
    info(f"Using fieldId={verifies_field_id}, type={verifies_field_type}")

    # Attempt 1: Full payload (our current implementation)
    payload1 = {
        "fieldValues": [{
            "fieldId": verifies_field_id,
            "name": "Verifies",
            "type": "FieldReference",
            "values": [{"id": req_item_id}]
        }]
    }
    info(f"\nAttempt 1 — Full payload:")
    info(json.dumps(payload1, indent=2))
    r = _put(f"/v3/items/{tc_item_id}/fields", payload1)
    info(f"  → {r.status_code}")
    if r.status_code == 200:
        ok("Attempt 1 SUCCESS — Full payload works")
        ok(f"✅ PHASE 1A CONFIRMED: PUT /v3/items/{{id}}/fields with fieldId={verifies_field_id}, type=FieldReference")
        return
    else:
        info(f"  Response: {r.text[:200]}")

    # Attempt 2: Minimal (no name/type)
    payload2 = {"fieldValues": [{"fieldId": verifies_field_id, "values": [{"id": req_item_id}]}]}
    info(f"\nAttempt 2 — Minimal (no name/type):")
    info(json.dumps(payload2))
    r = _put(f"/v3/items/{tc_item_id}/fields", payload2)
    info(f"  → {r.status_code}: {r.text[:150]}")
    if r.status_code == 200:
        ok("Attempt 2 SUCCESS — Minimal payload works")
        return

    # Attempt 3: TrackerItemReference type
    payload3 = {"fieldValues": [{"fieldId": verifies_field_id, "name": "Verifies", "type": "TrackerItemReference", "values": [{"id": req_item_id}]}]}
    info(f"\nAttempt 3 — type=TrackerItemReference:")
    info(json.dumps(payload3))
    r = _put(f"/v3/items/{tc_item_id}/fields", payload3)
    info(f"  → {r.status_code}: {r.text[:150]}")
    if r.status_code == 200:
        ok("Attempt 3 SUCCESS — TrackerItemReference type works")
        return

    # Attempt 4: Using PUT /v3/items/{id} with references
    payload4 = {"upstreamReferences": [{"id": req_item_id}]}
    info(f"\nAttempt 4 — PUT /v3/items/{{id}} with upstreamReferences:")
    info(json.dumps(payload4))
    r = _put(f"/v3/items/{tc_item_id}", payload4)
    info(f"  → {r.status_code}: {r.text[:150]}")
    if r.status_code == 200:
        ok("Attempt 4 SUCCESS — upstreamReferences on item update works")
        return

    # Attempt 5: POST /v3/associations
    payload5 = {"from": {"id": tc_item_id}, "to": {"id": req_item_id}, "type": {"id": 2}}
    info(f"\nAttempt 5 — POST /v3/associations:")
    info(json.dumps(payload5))
    r = _post("/v3/associations", payload5)
    info(f"  → {r.status_code}: {r.text[:200]}")
    if r.status_code in (200, 201):
        ok("Attempt 5 SUCCESS — Associations API works (but different approach)")
        return

    fail("All attempts failed")
    raise Exception("Could not set Verifies relationship via any method")

# ═══════════════════════════════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("CB API Validation v3 — Targeted Field Test")
    print(f"Instance: {CB_URL}")
    print("=" * 60)

    test("1. Find REQ + TC items", test_find_items)
    test("2. Discover fields on TC item", test_discover_fields)
    test("3. Set Verifies field (5 approaches)", test_set_verifies)

    print(f"\n{'=' * 60}")
    print("RESULTS SUMMARY")
    print("=" * 60)
    all_pass = True
    for name, status in results:
        icon = "✅" if status == "PASS" else "❌"
        print(f"  {icon} {name}: {status}")
        if status != "PASS":
            all_pass = False

    if all_pass:
        print(f"\n🎉 ALL TESTS PASSED")
    else:
        print(f"\n⚠️  SOME TESTS FAILED — check details above")

    print("=" * 60)
    print("\nPlease paste this full output back to Claude.")
