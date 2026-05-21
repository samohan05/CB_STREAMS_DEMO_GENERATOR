# Test Plan — Codebeamer ALM Demo Generator

**For:** Claude for Chrome (browser automation agent)
**Target app:** http://127.0.0.1:5000/
**Mode:** DRY-RUN ONLY — do not switch to live mode. Cleanup endpoints can delete real Codebeamer data; never click "Execute Cleanup".

---

## ⚠️ Context budget — read this before you start

The previous run exhausted the 1M-token context limit because it accumulated every console message and network request in working memory. To finish this run in one session, follow these rules:

1. **Write findings to disk incrementally.** After every phase (Pre-flight, Phase A, Phase B, Phase C, Cross-cutting), update `TEST_REPORT.html` immediately with that phase's rows. Do NOT wait until the end. Re-read the file before each update.
2. **Never paste raw console output, raw network bodies, raw HTML, or full screenshots into the conversation.** When you need to inspect, use the smallest possible tool (e.g. `mcp__Claude_in_Chrome__find` for a single element, not `read_page`).
3. **Console reads:** filter to `error` level only. Cap at the first 10 entries. Do not read warnings.
4. **Network reads:** filter to non-2xx responses only. Cap at the first 10.
5. **Screenshots:** save to `screenshots/T##_short-name.png`. Do not embed inline data URIs. Just reference the file path in the report.
6. **Test execution:** one test at a time. After each test, decide PASS/FAIL/WARN immediately, write to disk, drop the page state from working memory, move on.
7. **If you hit ~700K tokens internally**, stop, write the partial report with whatever you've completed, mark remaining tests as `SKIP — context budget`, and exit cleanly.

---

## Preconditions

**P1.** Open http://127.0.0.1:5000/ in a fresh tab.
- Expected: page loads in under 3 seconds; no full-page error.
- Critical first check: the page should land on the **marketing landing page** (hero section with gradient background and "Launch the Generator" button), NOT directly on the wizard.
- If connection refused → STOP, write a one-row report, exit.

**P2.** Console errors on initial paint: read errors only, cap 10. Note count.

**P3.** Confirm `/api/config` returned 200 in the network panel (one-shot lookup, do not dump the body).

---

## PHASE A — Landing page (marketing walkthrough)

The landing page is what the user (Mohan) will walk a room through. Each section is a verbal beat. Verify all sections render correctly.

### T01. Hero section
- **Action:** Look at the top of the page.
- **Expected:**
  - Dark gradient panel (navy → blue) with rounded corners.
  - Codebeamer wordmark image at the top-left of the panel (white-inverted), OR if missing a styled text "Codebeamer." in white as fallback.
  - Green uppercase eyebrow text: "ALM DEMO GENERATOR · PRE-SALES TOOLING".
  - Large white headline: "A credible Codebeamer demo environment, ready before your customer joins the call."
  - Supporting paragraph below.
  - Primary green button labeled "Launch the Generator →" with a soft drop shadow.
  - Caption next to button: "Internal PTC pre-sales tool · Sandboxes only".
- **Screenshot:** `screenshots/T01_hero.png`.

### T02. Stats band
- **Action:** Scroll down one section.
- **Expected:** Four white cards with green top-border accent, showing: `< 3 min` / `8` / `4-tier` / `60+`. Each has an uppercase tertiary-color label below.

### T03. "What it does" feature grid
- **Action:** Continue scrolling.
- **Expected:**
  - Green uppercase eyebrow "WHAT IT DOES" + dark headline "Six things you previously hand-built before every demo."
  - 3-column grid of exactly 6 feature cards. Each card has an emoji icon, a bold title, and a supporting paragraph.
  - Titles are benefit-led (e.g. "End-to-end traceability, generated in under three minutes.").

### T04. "How it works" workflow
- **Action:** Continue scrolling.
- **Expected:**
  - Eyebrow "HOW IT WORKS" + headline "A five-step wizard…".
  - Single panel with `bg-secondary` background containing 5 columns.
  - Each column has: a numbered green circle (36px diameter, white digit), bold step title, supporting paragraph.
  - Arrows (→) sit between adjacent columns, anchored at the top of each column's content area.
  - Arrows must NOT overlap any step's title text.
- **Screenshot:** `screenshots/T04_workflow.png`.

### T05. Capabilities vs Limitations
- **Action:** Continue scrolling.
- **Expected:**
  - Two side-by-side panels of equal width.
  - LEFT panel: green left-border (4px), eyebrow "WHAT IT DOES WELL", headline "Confidence to bring it into the room.", a list of 9 items each with a green ✓ check mark.
  - RIGHT panel: orange left-border (4px), eyebrow "WHERE IT STOPS", headline "Limits we name up front…", a list of 5 items each with an orange ! marker.
  - The two panels visually balance each other — this is the "honesty signal" beat.
- **Screenshot:** `screenshots/T05_capabilities_limits.png`.

### T06. Personas
- **Action:** Continue scrolling.
- **Expected:** 3-column grid of cards on `bg-secondary` background. Each card has a 2px GREEN left-border, a navy-colored persona name in bold, and an italic-leading sentence starting with "…".

### T07. Final CTA
- **Action:** Scroll to bottom.
- **Expected:** Dark navy gradient panel with white headline "Stop rebuilding the same demo. Spend the time on the customer instead.", a caption with a `samohan@ptc.com` mailto link in light green, and a green "Launch the Generator →" button.

### T08. CTA hover lift
- **Action:** Hover over the primary green "Launch the Generator" button in the hero (do not click).
- **Expected:** Button rises ~1px and shadow intensifies. Effect is subtle, smooth (~150ms).

---

## PHASE B — Landing ↔ Tool router

### T09. Launch into the wizard
- **Action:** Click the "Launch the Generator →" button (hero or final CTA — either works).
- **Expected:**
  - Landing page fades out, wizard appears at Step 0.
  - StepBar visible at top showing 5 steps.
  - LIVE-MODE/DRY-RUN banner appears (it must say **DRY RUN**, not LIVE — if LIVE, STOP and abort).
  - Header now shows a small "← About this tool" green link below the subtitle.
- **Screenshot:** `screenshots/T09_wizard_step0.png`.

### T10. Round-trip — back to landing, back to wizard
- **Action:** Click "← About this tool" in the header.
- **Expected:** Returns to landing page; wizard chrome (StepBar, DRY-RUN banner, About link) hidden.
- **Action:** Click "Launch the Generator →" again.
- **Expected:** Returns to the wizard at Step 0 (or wherever you were — state preserved). DRY-RUN still active.

---

## PHASE C — Wizard happy-path & bug-fix verification (DRY RUN ONLY)

### T11. Step 0 — domain pick
- **Action:** On Step 0, click the "Medical Devices" product tile (or first available).
- **Expected:** The tile shows a selected state (filled background or colored border). A "Next →" button appears or auto-advance happens.

### T12. Step 1 — CB Connection fields
- **Action:** Advance to Step 1.
- **Expected:**
  - "CB Connection" section with three inputs: CB Base URL (pre-populated `https://...`), CB User (pre-populated), CB Password (masked).
  - "OpenAI" section below.
  - "Next →" button.

### T13. BUG-FIX VERIFICATION — CB credential headers (Phase 3 #2)
- **Action:**
  1. Open the network panel; filter for `/api/cb/`.
  2. In the DevTools console, paste and run:
     ```js
     fetch('/api/cb/v3/projects', { headers: { 'X-CB-Url': 'https://override-test.example:9443', 'X-CB-User': 'tester', 'X-CB-Pass': 'p' }})
       .then(r => 'fetch returned status ' + r.status);
     ```
  3. In the network panel, click the resulting `/api/cb/v3/projects` request → Headers → Request Headers.
- **Expected:** The request carries `X-CB-Url`, `X-CB-User`, and `X-CB-Pass` headers. If absent, the Phase 3 #2 fix did not land — mark FAIL.
- **Capture:** Just the three header names + a 1-line note. Do not paste the whole header block into the report.

### T14. Step 2 — Generate (dry run)
- **Action:** From Step 1, click "Next →" then click "Generate Structure" (or equivalent) on Step 2.
- **Expected:**
  - Codebeamer logo in header begins a heartbeat pulse animation (subtle ~1.4s scale cycle).
  - Stage indicator shows progress.
  - After 10–60s, the structure preview appears. Heartbeat stops.
  - Zero new console errors during the call (count only — do not dump).

### T15. Advance to Step 4
- **Action:** Click through Steps 2 → 3 → 4. In DRY RUN, "Create All" buttons are safe.
- **Expected:** Arrive at Step 4 "Demo Summary".

### T16. Step 4 — Stat band + tabs visible
- **Action:** Look at Step 4 layout.
- **Expected:**
  - 4 colored stat cards at the top.
  - Tab pill showing "Projects | Streams | Lineage" with Projects active (green background, white text).
  - Right side: "Group by tier" toggle + "Collapsed/Expanded" pill.
  - Filter band below with search input + 4 tier pills.

### T17. Tab switching with fade-in
- **Action:** Click "Streams" then "Lineage".
- **Expected:** Each switch triggers a subtle fade-in (~160ms). Lineage shows an SVG diagram with 4 columns and connecting arrows. Filter band HIDDEN on Lineage.
- **Screenshot:** `screenshots/T17_lineage.png`.

### T18. BUG-FIX VERIFICATION — Expand/Collapse precedence (Phase 3 #1)
- **Action:** Return to "Projects" tab. With "Collapsed" chip active (default), click on 2 individual project cards to expand them manually. Then click "Expanded" in the chip. Then click "Collapsed" in the chip.
- **Expected:** After clicking "Collapsed", **every** card collapses, including the two you manually expanded. If any card remains expanded → FAIL.

### T19. Filter pane — name search
- **Action:** Type a partial name into the search input that matches at least one card.
- **Expected:** List narrows. "✕ Clear filters" link appears.

### T20. Filter pane — tier toggle + active state
- **Action:** Clear search. Click the "Library" tier pill.
- **Expected:** Pill becomes SOLID (tier color background, white text, leading ✓). List filters to Library-category projects only.

### T21. Group by tier
- **Action:** Click "▢ Group by tier" (right side of tab row).
- **Expected:** Button becomes "▣ Grouped by tier" in green. Projects regroup under tier headers (Library, Product Line, Release) each with a colored dot + count.
- **Screenshot:** `screenshots/T21_grouped.png`.

### T22. Empty state
- **Action:** Type gibberish ("zzqqxx") in the search input.
- **Expected:** Both Projects (or Streams, if active) tab shows a dashed-border empty-state card: "No projects/streams match the current filter. Clear filters" — link in PTC green.

### T23. Clear filters
- **Action:** Click "✕ Clear filters" link.
- **Expected:** All pills reset, search clears, full list returns.

### T24. BUG-FIX VERIFICATION — Print captures all tabs (V-07/F-01)
- **Action:** Switch to the "Lineage" tab. Click "🖨 Print" in the top-right of Step 4.
- **Expected:**
  - Print preview opens.
  - Preview content shows **Projects + Streams + Lineage** stacked, NOT just Lineage.
  - Tabs, expand chip, filter band hidden in the print preview.
- **Action:** Close the print dialog WITHOUT printing.

### T25. Export HTML
- **Action:** Click "↓ Export HTML".
- **Expected:** A file downloads (filename like `codebeamer-demo-summary-*.html`). Do not open it — just confirm the download started.

---

## Cross-cutting

### T26. Reduced-motion respect
- **Action:** Open DevTools → Rendering → set "Emulate CSS media feature `prefers-reduced-motion`" to "reduce". Click a Step 4 tab.
- **Expected:** No fade-in animation. Reset the emulation after.

### T27. Final console + network summary
- **Action:** Read console **errors only**, cap 10. Read network **non-2xx only**, cap 10.
- **Expected:** Zero red errors. Zero 4xx/5xx (except possibly a `/favicon.ico` 404 which is tolerable).
- **Capture:** Just the counts and a 1-line summary. Do not paste raw output.

---

## HTML REPORT — TEST_REPORT.html

**Write this file incrementally — after each phase, re-read and append.** Final file lives at the project root.

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Codebeamer ALM Demo Generator — Test Report</title>
<style>
  :root { --green:#40AA1D; --red:#DC2626; --amber:#D97706; --slate:#617480; --bg:#F7F7F4; --card:#FFFFFF; --border:#E5E5E0; --navy:#1D496E; }
  * { box-sizing:border-box; }
  body { font-family:Raleway,-apple-system,"Segoe UI",sans-serif; margin:0; padding:24px; background:var(--bg); color:#1D2025; }
  h1 { margin:0 0 4px; font-size:24px; }
  .meta { color:var(--slate); font-size:13px; margin-bottom:24px; }
  .summary { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:28px; }
  .stat { padding:16px; background:var(--card); border:1px solid var(--border); border-radius:8px; }
  .stat .n { font-size:28px; font-weight:600; }
  .stat .l { font-size:11px; color:var(--slate); text-transform:uppercase; letter-spacing:0.6px; margin-top:4px; }
  .stat.pass .n { color:var(--green); }
  .stat.fail .n { color:var(--red); }
  .stat.warn .n { color:var(--amber); }
  table { width:100%; border-collapse:collapse; background:var(--card); border:1px solid var(--border); border-radius:8px; overflow:hidden; margin-bottom:16px; }
  th, td { padding:10px 14px; font-size:13px; text-align:left; border-bottom:1px solid var(--border); vertical-align:top; }
  th { background:#F2F2EE; font-weight:600; }
  tr:last-child td { border-bottom:none; }
  .badge { display:inline-block; padding:2px 8px; border-radius:10px; font-size:11px; font-weight:600; }
  .badge.pass { background:#E8F5E0; color:var(--green); }
  .badge.fail { background:#FEE2E2; color:var(--red); }
  .badge.warn { background:#FEF3C7; color:var(--amber); }
  .badge.skip { background:#E5E7EB; color:var(--slate); }
  .phase-header { margin-top:32px; margin-bottom:8px; font-size:16px; font-weight:600; color:var(--navy); }
  .screenshot { max-width:280px; max-height:160px; border:1px solid var(--border); border-radius:4px; margin-top:6px; }
  pre { background:#F2F2EE; padding:8px; border-radius:4px; font-size:11px; overflow-x:auto; }
</style>
</head>
<body>
  <h1>Codebeamer ALM Demo Generator — Test Report</h1>
  <div class="meta">Generated <!-- ISO-8601 timestamp --> · Run by Claude for Chrome · Landing page + Phases 1+2+3</div>

  <div class="summary">
    <div class="stat pass"><div class="n">N</div><div class="l">Passed</div></div>
    <div class="stat fail"><div class="n">N</div><div class="l">Failed</div></div>
    <div class="stat warn"><div class="n">N</div><div class="l">Warnings</div></div>
    <div class="stat"><div class="n">N</div><div class="l">Skipped</div></div>
  </div>

  <div class="phase-header">Phase A — Landing page</div>
  <table><thead><tr><th style="width:60px">ID</th><th>Test</th><th style="width:80px">Result</th><th>Observation</th></tr></thead><tbody>
    <!-- T01..T08 rows -->
  </tbody></table>

  <div class="phase-header">Phase B — Router</div>
  <table><thead>…</thead><tbody><!-- T09..T10 --></tbody></table>

  <div class="phase-header">Phase C — Wizard + bug-fix verification</div>
  <table><thead>…</thead><tbody><!-- T11..T25 --></tbody></table>

  <div class="phase-header">Cross-cutting</div>
  <table><thead>…</thead><tbody><!-- T26..T27 --></tbody></table>

  <div class="phase-header">Defects Found</div>
  <table>
    <thead><tr><th>ID</th><th>Severity</th><th>Test ref</th><th>What broke</th><th>Repro</th></tr></thead>
    <tbody>
      <!-- one row per FAIL or WARN; if zero defects use a single italic-grey "No defects found" row -->
    </tbody>
  </table>

  <div class="phase-header">Console & Network Summary</div>
  <p>Console errors: <strong>N</strong>. <em>(top entries, if any)</em></p>
  <pre><!-- 1-3 lines max --></pre>
  <p>Non-2xx network responses: <strong>N</strong>.</p>
  <pre><!-- 1-3 lines max --></pre>

  <div class="phase-header">Verdict</div>
  <p><!-- one paragraph; if zero S1/S2 → "Ready to demo"; if any S1 → "DO NOT DEMO"; if only S3/S4 → "Ready with known cosmetic gaps" --></p>
</body>
</html>
```

**Filling rules:**
- Result badge classes: `pass`, `fail`, `warn`, `skip`.
- Severity column: **S1** demo-blocker · **S2** customer-noticeable · **S3** polish · **S4** cosmetic.
- Observation cells: ≤ 2 sentences. Reference a screenshot path if relevant; do not embed image data.
- Save at: `C:\Users\samohan\Documents\Claude\Projects\Philips\Codebeamer_Streams_Demo_Generator\TEST_REPORT.html`.

---

## DO NOT do these

- Do NOT click "Execute Cleanup" (deletes real CB projects).
- Do NOT switch the dry-run banner to LIVE MODE.
- Do NOT modify the CB password field with a real value.
- Do NOT close the browser or navigate away mid-run.
- Do NOT dump raw HTML, raw console messages, or raw network bodies into the conversation.
- Do NOT wait until the end to write the report — write incrementally.

---

## If you hit the context limit anyway

Stop. Open `TEST_REPORT.html`. For every test row still missing, fill it with:

```
<td>T##</td><td>Test name</td><td><span class="badge skip">SKIP</span></td><td>Skipped — agent context budget exhausted at this point in the run.</td>
```

Save the file. Report back: "Partial run — N of 27 tests completed; report saved at TEST_REPORT.html."
