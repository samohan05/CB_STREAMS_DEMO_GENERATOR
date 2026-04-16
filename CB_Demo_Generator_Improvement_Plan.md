# CB Demo Generator — Phased Improvement Plan

**File:** `cb_demo_generator.jsx`
**Goal:** Production-quality demo automation tool that generates a correct, secure, hierarchical Codebeamer provisioning script.

---

## Phase 1: Fix the Python Script Core (Generated Code Correctness)

> **Why first:** The Python script is the deliverable your customers run. Everything else is UI around it. Get the generated code right before polishing the generator.

### 1A. Replace `set_verifies` with `PUT /v3/items/{itemId}/fields`

The current code uses `upstreamReferences` on PUT /v3/items, which is unreliable. Replace with the field-level API using the Verifies field (ID 17, type FieldReference):

```python
def set_verifies(tc_id, req_id):
    """PUT /v3/items/{itemId}/fields
    Sets the 'Verifies' field (fieldId=17, type=FieldReference) on a test case
    to reference the requirement it verifies."""
    if not tc_id or not req_id:
        return
    try:
        _put(f"/v3/items/{tc_id}/fields", {
            "fieldValues": [{
                "fieldId": 17,
                "name": "Verifies",
                "type": "FieldReference",
                "values": [{"id": req_id}]
            }]
        })
        ok(f"    [VERIFIES] TC {tc_id} --verifies--> REQ {req_id}")
    except Exception as e:
        warn(f"    [VERIFIES] TC {tc_id} -> REQ {req_id}: {e}")
```

**Tasks:**
- [ ] Replace the `set_verifies` function in `buildPythonScript()` (lines 247–257)
- [ ] Add `VERIFIES_FIELD_ID = 17` as a configurable constant alongside `REQ_TYPE_ID` and `TC_TYPE_ID`
- [ ] Update the script header docstring to reference `PUT /v3/items/{id}/fields` instead of associations

### 1B. Establish Stream Hierarchy via `sourceStreamId`

Currently all streams are created as flat siblings. The `CreateStream` schema accepts `sourceStreamId` — use it to wire Library → PL → Transform → Release.

```python
def mk_stream(name, desc="", source_id=None):
    body = {"name": name, "color": STREAM_COLOR, "description": desc}
    if source_id:
        body["sourceStreamId"] = source_id
        body["isSourceStreamChecked"] = True
    r = _post("/v3/streams/stream", body)
    ok(f"[STREAM] {name}  id={r['id']}" + (f"  parent={source_id}" if source_id else ""))
    return r["id"]
```

**Tasks:**
- [ ] Modify `mk_stream()` to accept an optional `source_id` parameter
- [ ] Update `buildPythonScript()` to pass parent stream IDs when creating child tiers:
  - PL streams receive the first Library stream ID as `source_id`
  - Transform streams receive their corresponding PL stream ID
  - Release streams receive their corresponding Transform stream ID
- [ ] Track stream IDs per tier using Python variables in the generated code

### 1C. Secure Credential Handling

Replace hardcoded credentials with environment variables.

**Tasks:**
- [ ] Change generated Python to read `CB_URL`, `CB_USER`, `CB_PASS` from `os.environ`
- [ ] Add startup validation that prints a clear message if env vars are missing
- [ ] Still allow the UI fields to set *default* values as comments in the script
- [ ] Remove password from the script entirely — only env var

### 1D. Add Retry Wrapper with Rate-Limit Handling

**Tasks:**
- [ ] Create a unified `_request(method, path, body)` function with:
  - 3 retries on 429 (Too Many Requests) with exponential backoff
  - 1 retry on 500/503 (transient server errors)
  - Clear error message on 401 (bad credentials) — no retry
- [ ] Replace `_get`, `_post`, `_put` with calls through the retry wrapper
- [ ] Remove the lone `time.sleep(0.07)` in `mk_item` — the retry wrapper handles pacing

**Deliverable:** A generated Python script that creates a hierarchical stream structure, correctly links TCs to requirements via field references, reads credentials from env vars, and handles API rate limits.

---

## Phase 2: Fix the Generator (React/JSX Correctness)

> **Why second:** Now that the generated Python is correct, fix the generator that produces it.

### 2A. Resolve AI API Authentication

The `fetch` to `api.anthropic.com` is missing `x-api-key` and `anthropic-version` headers.

**Decision needed:** How will this component be deployed?

- **Option A — Claude Artifact / Embedded:** Remove the direct API call entirely. Instead, accept pre-generated JSON as a prop or via paste. The AI generation happens in the chat conversation, not in the component.
- **Option B — Standalone React App:** Add an API key input field (stored in memory only, never in the script). Add the required headers. Add a disclaimer about client-side key usage.
- **Option C — With Backend Proxy:** The fetch goes to a proxy endpoint (e.g., `/api/generate`) that holds the API key server-side. Most secure.

**Tasks (assuming Option A for fastest path):**
- [ ] Add a "Paste JSON" mode as an alternative to AI generation
- [ ] If keeping AI generation, add `x-api-key` and `anthropic-version: 2023-06-01` headers
- [ ] Add API key input field to the CB Config step (Step 1), stored only in React state
- [ ] Never write the Anthropic API key into the generated Python script

### 2B. Increase `max_tokens` and Tune the Prompt

**Tasks:**
- [ ] Change `max_tokens` from 1000 to 4096
- [ ] Add `"anthropic-version": "2023-06-01"` to the request headers
- [ ] Test with each template to verify JSON completeness without truncation
- [ ] Consider adding a `temperature: 0.3` parameter for more consistent structure

### 2C. Fix Minor Bugs

**Tasks:**
- [ ] **Emoji animation (line 684):** Add a `useEffect` with `setInterval` to cycle the emoji during step 2
- [ ] **Variable shadowing (line 115):** Rename local `esc` in `sanitizeJson` to `isEscaped`
- [ ] **project_key inconsistency:** Align on 8-char max in both the prompt and `mk_project` (currently prompt says 8, code uses `key[:16]`)

**Deliverable:** A generator that successfully calls the AI (or accepts pasted JSON), produces complete output, and has no UI bugs.

---

## Phase 3: Robustness & Demo Quality

> **Why third:** With a working end-to-end flow, harden it for real customer demos.

### 3A. Add Idempotency to Generated Script

**Tasks:**
- [ ] Before `mk_project`, check if a project with that key already exists via `GET /v3/projects` with search
- [ ] If project exists, reuse its ID instead of creating a duplicate
- [ ] Add a `--clean` flag that deletes previously created demo projects before recreating
- [ ] Add a `--dry-run` flag that prints the plan without executing API calls

### 3B. Add Configurable Field IDs

The Verifies field ID (17) and tracker type IDs (5, 102) may differ across CB instances.

**Tasks:**
- [ ] Add a "Discover" step to the generated script: `GET /v3/trackers/types` and `GET /v3/items/{itemId}/fields` to auto-detect IDs
- [ ] Fall back to constants if discovery fails
- [ ] Add these as configurable in the UI (advanced settings accordion)

### 3C. Add Validation and Summary

**Tasks:**
- [ ] After script execution, query all created items and verify counts match expectations
- [ ] Print a summary table: streams created, projects, requirements, test cases, verifies links
- [ ] Flag any items that failed creation with specific error details

**Deliverable:** A script that can be run repeatedly without creating duplicates, auto-discovers field IDs, and validates its own output.

---

## Phase 4: Code Quality & Maintainability

> **Why last:** Refactoring that doesn't change behavior — do it once the behavior is correct.

### 4A. Extract Modules

**Tasks:**
- [ ] `templates.js` — TEMPLATES and TIERS constants
- [ ] `prompt.js` — `buildPrompt()` function
- [ ] `jsonParser.js` — `sanitizeJson()` and `parseAIJson()`
- [ ] `pythonBuilder.js` — `buildPythonScript()` and all helper generation logic
- [ ] `components/` — Steps, Stat, StreamTree as separate component files

### 4B. Add TypeScript Types

**Tasks:**
- [ ] Define interfaces for Stream, Project, Requirement, TestCase, DemoStructure
- [ ] Type the AI response parsing pipeline
- [ ] Type the Python builder input/output

### 4C. Template the Python Script

**Tasks:**
- [ ] Replace string concatenation with a template engine (e.g., Mustache or tagged template literals)
- [ ] Store the Python script skeleton as a template file
- [ ] Inject only the variable parts (stream names, project keys, etc.)

**Deliverable:** Clean, modular, typed codebase that's easy to extend with new domain templates or CB API versions.

---

## Execution Order Summary

| Phase | Focus | Key Outcome | Estimated Effort |
|-------|-------|-------------|-----------------|
| **1** | Generated Python correctness | Script creates proper hierarchy with field-level verifies links | 2–3 hours |
| **2** | Generator/React fixes | End-to-end flow works reliably | 1–2 hours |
| **3** | Robustness | Idempotent, auto-discovering, self-validating | 2–3 hours |
| **4** | Code quality | Modular, typed, maintainable | 2–3 hours |

**Recommendation:** Complete Phases 1 and 2 together as a single working session — they produce a fully functional tool. Phases 3 and 4 can be done incrementally.
