# Archive

Files in this directory are **superseded** and not part of the active codebase.

The active app is the Flask + React local server (`server.py` + `cb_demo.html` in the project root).

## Why these are archived

The original architecture was a 3-layer design:

1. Browser-only React component (`cb_demo_generator.jsx`) running inside a Claude.ai artifact.
2. Direct call from the browser to the Anthropic Claude API (blocked by CORS, missing auth headers).
3. A downloadable Python script (`cb_demo_MR.py`-style) that the user ran locally to provision Codebeamer.

That architecture was replaced by an interactive Flask + React local server that provisions CB directly through a proxy. The files in this folder belong to the old design and are kept for reference only.

## Inventory

| File | Old role |
|---|---|
| `cb_demo_generator.jsx` | Original 973-line React artifact — superseded by `cb_demo.html` |
| `cb_demo_MR.py` / `cb_demo_MR.txt` | Hand-written Python demo provisioning script |
| `cb_api_validation.py` / `_v2.py` / `_v3.py` | Three iterations of standalone CB API validation scripts |
| `prompt.js`, `pythonBuilder.js`, `templates.js`, `helpers.js`, `jsonParser.js` | Modules extracted from the old `.jsx` per the now-obsolete improvement plan |
| `cb_demo_core.js`, `cb_demo_core.test.js` | Old core logic + Vitest suite for the script-builder approach |
| `cb_demo.log` | Old debug log from a prior session |

## Do not import from this folder

The active app does not depend on anything here. Treat this directory as historical only.
