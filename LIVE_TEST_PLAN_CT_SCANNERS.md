# LIVE-MODE Test Plan — CT Scanners domain

**For:** Claude for Chrome
**Target:** http://127.0.0.1:5000/
**Mode:** **LIVE** — real Codebeamer API calls. Real artifacts will be created. Cleanup is the consultant's responsibility, not yours.
**Estimated duration:** 12–18 minutes (most of it spent on the 30 s stream pacing).
**Report file:** `LIVE_TEST_REPORT.html` at the project root.

---

## ⚠️ Context budget (read first)

The previous run exhausted the 1 M-token cap by buffering raw output. Follow these rules or you will not finish:

1. **Write `LIVE_TEST_REPORT.html` incrementally after every numbered step.** Append one row at a time. Never wait until the end.
2. **Never paste raw HTML, raw network bodies, raw console text, or full screenshots into the chat.** Reference saved screenshot paths only.
3. **Console reads:** errors only, cap 5.
4. **Network reads:** non-2xx only, cap 5.
5. **Screenshots:** save to `screenshots/L##_short.png`. Do not embed.
6. **Polling waits:** when waiting for a button or status to change, poll every 2 s with a single `find` call, max 60 s. Do not `read_page` while waiting.
7. **If you cross ~600 K tokens**, stop, finish the partial report, mark remaining steps `SKIP — context budget`, exit.

---

## ⚠️ Live-mode safety

- Do NOT click **Execute Cleanup** — that deletes real CB data. Cleanup is the user's call after the demo.
- Do NOT change CB URL, user, or password in the UI unless step explicitly says so.
- If a step says "wait for status", wait. Do not skip ahead. Live operations are slow.
- If a step times out (status doesn't change after the polling window), mark the test FAIL with the timing observed and continue with the next step. Do NOT abort the whole run — partial reports are valuable.

---

## L00. Pre-flight

1. Open http://127.0.0.1:5000/ in a fresh tab.
2. Confirm landing page renders (hero with green "Launch the Generator" button). If wizard chrome appears instead, the routing changed — abort and report.
3. Click **Launch the Generator →**. Confirm wizard appears at Step 0 and the banner reads **DRY RUN** (default).
4. Record start timestamp.

---

## L01. Pick domain — CT Scanners

1. At Step 0, look at the product tile grid. Find a "Medical Imaging" tile.
   - If found → click it. Then look for a sub-domain / model field on the next sub-screen and enter `CT Scanners`. If no sub-field exists, the template likely covers CT alongside MRI/PET — that is acceptable; proceed.
   - If "Medical Imaging" tile is **not** present → click the "Custom domain" / "Other" tile. In the domain field type `CT Scanners`. In the industry field (if separate) type `Medical Imaging`.
2. Advance to Step 1 ("Next →" or auto-advance).
3. **Report row:** PASS if Step 1 reached with the CT Scanners domain selected. Note which path you took (Medical Imaging template vs Custom domain).

---

## L02. Step 1 — CB Connection check (do NOT edit)

1. Confirm three populated inputs: CB Base URL (https://…), CB User, CB Password (masked).
2. Confirm an OpenAI section exists below.
3. Do NOT edit any field — the env-default credentials must be used for this test.
4. **Report row:** PASS / FAIL based on whether all three are non-empty.

---

## L03. Flip to LIVE mode

1. Locate the DRY-RUN / LIVE toggle near the banner under the header subtitle. It is a checkbox or switch with the label "Dry Run" / "Live".
2. Click it so the banner text changes from "DRY RUN" to "LIVE MODE".
3. The banner background should turn green (was amber in dry-run).
4. **Report row:** PASS if banner now reads "LIVE MODE — Create buttons will make real API calls to Codebeamer." FAIL if any text says DRY RUN.
5. **If you cannot find the toggle**, mark FAIL, save the report, and stop. The rest of the plan depends on this.

---

## L04. Step 2 — Generate structure

1. Advance to Step 2 ("Next →").
2. Click **Generate Structure** (or whatever the primary green button on Step 2 reads).
3. Watch the Codebeamer logo in the header — it should begin a heartbeat pulse.
4. **Poll every 3 s, max 90 s**, for the structure preview to render. The preview shows a list of project + stream names grouped by tier.
5. When preview appears:
   - Count projects in the preview. Record the count.
   - Confirm 4-tier hierarchy is visible (Library, Product Line, Transform, Release groups).
6. **Report row:** PASS if preview rendered with >= 8 projects across all tiers. Capture screenshot `L04_preview.png`.

---

## L05. Step 3 — Create All Projects

1. Advance to Step 3 ("Next →").
2. Find the **Create All Projects** button (the primary bulk action at the top of the projects list).
3. Click it.
4. **Poll every 3 s, max 180 s** (3 min), watching the per-project status badges. They should transition from "pending" → "creating" → "created" with a green check or numeric CB id.
5. When the bulk operation completes (all rows show created or some show error):
   - Count rows showing **created** (with an id like `id 12345`). Record.
   - Count rows showing **error**. If > 0, capture one error message verbatim (under 150 chars), record.
6. **Report row:**
   - PASS if 11/11 (or close — accept >= 9) created.
   - WARN if 1–2 errored.
   - FAIL if > 2 errored or the bulk button never enabled / never completed.

---

## L06. Step 3 — Create All Requirements (and test cases)

1. Scroll to the **Create All Requirements** section (or a button labeled similarly — may also create test cases in the same bulk action).
2. Click **Create All Requirements**.
3. **Poll every 3 s, max 240 s** (4 min). This step creates ~70 artifacts and is the slowest single bulk operation.
4. When complete:
   - Read the aggregate counts shown in the UI (total requirements created, total test cases, total Verifies links).
   - Record those three numbers.
5. **Report row:**
   - PASS if total artifacts >= 50 and zero errors.
   - WARN if 20–50 artifacts or 1–3 errors.
   - FAIL otherwise.

---

## L07. Step 3 — Stream creation (PACED, 30 s between streams)

This is the deliberate-pacing step. **Do not click "Create All Streams"** even if it exists. Instead, create each stream one at a time with a 30 s gap.

1. Locate the stream creation table on Step 3. Each row should have its own **Create** button (or a "+" / play glyph) for an individual stream.
2. **For each stream row, in display order (top to bottom):**
   a. Note the stream's tier and name (e.g. "Library · MR Imaging Library").
   b. Click that single row's Create button.
   c. **Poll every 2 s, max 30 s**, for that row's status to flip to "created" with a CB id.
   d. Once created (or after the 30 s polling window times out — mark that row error and move on):
      - Record `tier · name → id NN (PASS)` or `tier · name → ERROR (FAIL)`.
   e. **Sleep 30 seconds** before clicking the next row's Create button. Use whatever sleep / wait mechanism your runtime exposes. This is the deliberate pacing the user requested — do not skip it.
3. Continue until every row has been attempted.
4. **Report row:**
   - PASS if every stream got an id.
   - WARN if 1–2 streams errored.
   - FAIL if > 2 streams errored.
5. Capture one screenshot when complete: `L07_streams_done.png`.

**Why the 30 s pacing matters:** the user wants to observe each stream creation propagate to the Codebeamer instance one at a time, with breathing room for the CB backend and for visual inspection in a parallel CB tab. Do not optimise this away.

---

## L08. Advance to Step 4 — verify summary

1. Click **Next →** to advance to Step 4.
2. Confirm the 4 stat cards at the top show:
   - **Projects:** 11 (or close — accept >= 9)
   - **Requirements:** >= 30
   - **Test Cases:** >= 20
   - **Streams:** >= 8
3. Record each of the four numbers.
4. **Report row:** PASS / WARN / FAIL based on the above thresholds.

---

## L09. Step 4 tabs — quick sanity

For each tab below, click it, wait for fade-in, do a 3-second visual scan, click the next. Do NOT expand individual cards (saves time and context).

1. **Projects** — confirm rows render with CB ids in monospace.
2. **Streams** — confirm rows grouped by 4 tiers, each with CB ids.
3. **Lineage** — confirm SVG renders with at least one arrow between tiers.

**Report row per tab.**

---

## L10. Export HTML (handoff artifact)

1. Click **↓ Export HTML** in the top-right of Step 4.
2. Confirm a file downloads (filename like `codebeamer-demo-summary-*.html`).
3. **Do not open it** — that wastes context. Just confirm the download appeared in DevTools → Network or in the OS download notification.
4. **Report row:** PASS / FAIL.

---

## L11. Final state capture

1. Read console errors: errors only, cap 5. Record count.
2. Read network non-2xx: cap 5. Record count.
3. Record end timestamp. Compute elapsed minutes.

---

## DO NOT do these

- Do NOT click **Execute Cleanup**.
- Do NOT switch back to DRY-RUN mid-run.
- Do NOT close the browser tab.
- Do NOT edit CB URL / user / password.
- Do NOT click **Create All Streams** if it exists. Stream creation must be paced manually per L07.
- Do NOT navigate to the Codebeamer instance directly to "verify" projects exist — that costs context and is not necessary; the in-app status badges and ids are sufficient evidence.

---

## LIVE_TEST_REPORT.html — schema

Reuse the schema from `TEST_PLAN_FOR_CHROME.md` (same `:root` tokens, same table styling, same badge classes). Add one extra column to the test table: **"Duration"** (seconds for that step). The phase headers should be:

- Pre-flight & domain pick (L00–L02)
- Live-mode activation & generation (L03–L04)
- Bulk creation — projects & requirements (L05–L06)
- **Paced stream creation (L07)** — give this its own header even though it is one step, with a sub-table listing each individual stream and its outcome:

```html
<table>
  <thead><tr><th>Stream</th><th>Tier</th><th>CB id</th><th>Result</th><th>Wait observed</th></tr></thead>
  <tbody>
    <tr><td>MR Imaging Library</td><td>Library</td><td>1234</td><td><span class="badge pass">PASS</span></td><td>4 s create + 30 s pacing</td></tr>
    <!-- one row per stream -->
  </tbody>
</table>
```

- Verification & handoff (L08–L10)
- Cross-cutting (L11)

End the report with an **Analytics** section before the Verdict:

```html
<div class="phase-header">Analytics</div>
<table>
  <tbody>
    <tr><td>Total elapsed</td><td><strong>N minutes</strong></td></tr>
    <tr><td>Projects created</td><td>11 / 11</td></tr>
    <tr><td>Requirements created</td><td>N</td></tr>
    <tr><td>Test cases created</td><td>N</td></tr>
    <tr><td>Verifies links wired</td><td>N</td></tr>
    <tr><td>Streams created (paced)</td><td>N / N</td></tr>
    <tr><td>Average stream creation latency</td><td>N s (excluding pacing)</td></tr>
    <tr><td>Console errors</td><td>N</td></tr>
    <tr><td>Non-2xx responses</td><td>N</td></tr>
    <tr><td>Pass / Warn / Fail</td><td>P pass · W warn · F fail (of 12 steps)</td></tr>
  </tbody>
</table>
```

Save report at: `C:\Users\samohan\Documents\Claude\Projects\Philips\Codebeamer_Streams_Demo_Generator\LIVE_TEST_REPORT.html`.

---

## Verdict rule

- All steps PASS, zero console errors → **"Ready for customer demo."**
- 1–2 WARNs, zero FAILs → **"Ready with caveats — see analytics."**
- Any FAIL → **"Hold — investigate failures before customer-facing run."**

---

## If something goes wrong mid-run

- Live-mode error on a single bulk action → record it, continue to the next step. Do not retry inside the same run — that risks duplicate keys.
- Page freezes → record the step you were on, wait 60 s, refresh once. If the wizard returns to Step 0, the run is lost — save partial report, exit.
- Network panel shows repeated 401s → CB credentials are wrong; cannot complete. Save partial report, exit with "auth failure" note.

When you finish (or exit early), reply with one sentence summarising the verdict and the path to the report file. Nothing else in chat.
