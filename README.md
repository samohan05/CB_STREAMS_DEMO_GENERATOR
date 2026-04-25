# CB Demo Generator v4

AI-powered Codebeamer ALM pre-sales demo provisioning tool. Generates a complete, domain-specific 4-tier stream hierarchy in any Codebeamer instance — projects, requirements, test cases, traceability links, and the Library → Product Line → Transform → Release stream tree — in under 30 minutes.

![Architecture: Flask + React](https://img.shields.io/badge/Architecture-Flask_+_React-blue)
![Python 3.8+](https://img.shields.io/badge/Python-3.8+-green)
![License: Internal](https://img.shields.io/badge/License-Internal-yellow)

---

## What this tool does

A consultant picks a domain template (MRI, Ultrasound, ADAS, Pacemakers, etc., or a custom one), clicks **Generate**, and the tool calls OpenAI GPT-4o to produce a domain-specific structured plan: ~10 projects across three tiers (Library, Product Line, Release), each with shall-style requirements citing real standards (IEC 60601, IEC 62304, ISO 26262, DO-178C), measurable acceptance criteria, and concrete test cases.

The consultant then walks through a 5-step wizard. Each step writes to the customer's Codebeamer instance via a local Flask proxy — projects are created, requirements and test cases are populated with Verifies traceability, and the 4-tier stream hierarchy is built with per-project source-stream lineage. By the end, the customer's CB instance has a credible domain-accurate demo environment.

The tool was built for the Philips MR pre-sales engagement but is **domain-agnostic** — any consultant can use it for MedTech / Automotive / Aerospace.

---

## Architecture

```
┌──────────────────┐         ┌──────────────────┐         ┌──────────────────┐
│                  │  HTTP   │                  │  HTTPS  │                  │
│  Browser (React) │ ──────► │  Flask Backend   │ ──────► │  Codebeamer API  │
│  cb_demo.html    │ :5000   │  server.py       │         │  (your instance) │
│                  │         │                  │         │                  │
│  React 18 +      │         │   .env loader    │         └──────────────────┘
│  Babel-standalone│         │   SSRF allowlist │         ┌──────────────────┐
│  (no build step) │         │   Logging        │ ──────► │  OpenAI API      │
│                  │         │                  │         │  (GPT-4o)        │
└──────────────────┘         └──────────────────┘         └──────────────────┘
```

The Flask backend is a credentialed proxy — credentials live server-side in [.env](.env), the browser only talks to `localhost:5000`. SSRF protection allowlists only the specific Codebeamer paths the wizard needs.

### API routes (proxy)

| Browser request | Proxied to |
|---|---|
| `POST /api/openai/generate` | `https://api.openai.com/v1/chat/completions` |
| `GET/POST /api/cb/v3/{path}` | `{CB_URL}/cb/api/v3/{path}` (allowlisted paths only) |
| `GET/POST /api/cb/v1/{path}` | `{CB_URL}/cb/rest/{path}` (allowlisted paths only) |
| `GET /api/cb/api/{path}` | `{CB_URL}/cb/api/{path}` (only `projects/category`) |
| `GET /api/config` | Reports configured state without exposing secrets |
| `POST /api/cleanup/projects` | Lists or deletes projects in a CB category |
| `GET /api/cleanup/streams?prefix=X` | Lists streams whose names start with `[X]` (read-only — CB v3 doesn't allow stream delete) |
| `POST /api/log/new-session` | Rotates server-side log file per generation run |

---

## Prerequisites

- **Python 3.8+** with `pip`
- **OpenAI API Key** with access to `gpt-4o` (or `gpt-4o-mini` / `gpt-4-turbo`)
- **Codebeamer instance** with admin credentials (project + stream creation)
- A modern browser (Chrome, Edge, Firefox)

---

## Setup

### 1. Install Python dependencies

```bash
pip install flask requests
```

The .env loader is stdlib-only — no `python-dotenv` needed.

### 2. Configure credentials in `.env`

A `.env` file at the repo root holds all credentials. It's already in [.gitignore](.gitignore) so secrets never get committed.

If `.env` doesn't exist, create it with:

```bash
# CB Demo Generator — local credentials
CB_URL=https://your-codebeamer-instance:9443
CB_USER=admin
CB_PASS=your-cb-password
CB_VERIFY_SSL=false                 # true only if CB has a valid SSL cert
OPENAI_API_KEY=sk-...
FLASK_DEBUG=false                   # leave false for demos; true for dev
# PORT=5000
# HOST=127.0.0.1
```

Shell environment variables take precedence — useful for one-off overrides without editing the file.

### 3. Start the server

```bash
python server.py
```

You should see:

```
+--------------------------------------------------------------+
|  CB Demo Generator - Local Server                            |
+--------------------------------------------------------------+
|  Open: http://127.0.0.1:5000                                 |
+--------------------------------------------------------------+
|  CB_URL:         https://your-cb-instance:9443               |
|  CB_USER:        admin                                       |
|  CB_PASS:        set                                         |
|  OPENAI_KEY:     set                                         |
|  CB_VERIFY_SSL:  False                                       |
|  FLASK_DEBUG:    False                                       |
|  LOG_DIR:        .../logs                                    |
+--------------------------------------------------------------+
```

### 4. Open in browser

```
http://127.0.0.1:5000
```

---

## Usage — the 5-step wizard

### Dry Run vs Live mode

A toggle in the header banner switches between **Dry Run** (default — Create buttons simulate success without calling APIs) and **Live** (real CB writes). Once you click Generate, the toggle is **locked for the rest of the run** to prevent accidental mode switches mid-demo. To switch modes, click *Reset form* and start over.

### Step 0 — Product

- Pick one of 8 pre-configured Philips templates (MRI, Ultrasound, CT Scanner, IGT, Patient Monitoring, Radiotherapy, Pacemakers, ADAS) or enter a custom domain + industry.
- Verify Codebeamer connection details (pre-filled from `.env`).
- Set the **Stream name prefix** — every stream this run creates is tagged with `[<prefix>]` so you can find/group them later. Defaults to `YYMMDD-HHMM`. Leave blank to disable.
- Click **Generate Projects & Streams** to call GPT-4o for the structured plan.

### Step 1 — Projects

Generated plan is shown grouped by category (Library, Product Line, Release). Use individual **Create** buttons or **Create All** for batch creation.

- Projects are created via `POST /cb/rest/project` with the default project template (System Requirement Specification + Test Cases trackers).
- **Idempotency**: Before creation, the wizard checks if a project with the same name already exists in CB; if so, it reuses the project and resolves trackers instead of creating a duplicate.
- **Key-conflict retry**: If CB rejects a key as already-in-use, the wizard generates a new unique key and retries up to 3 times.
- **Sequential creation** with 10s pacing — CB needs time to finish background tracker provisioning before accepting the next project create.
- **Create All is disabled** while in flight — prevents accidental parallel API trains.

### Step 2 — Requirements & Test Cases

For each project the wizard creates:
- 5 System Requirements in the System Requirement Specification tracker
- 2 Test Cases in the Test Cases tracker
- **Verifies links** — TC1 verifies reqs 1–3, TC2 verifies reqs 4–5

The Verifies field is **dynamically discovered** from the Test Cases tracker schema (not hardcoded), so the wizard works across CB instances with different field IDs. The link is established via `PUT /v3/items/{id}/fields` with `UpdateTrackerItemField` body and `ChoiceFieldValue` referencing the requirement IDs.

### Step 3 — Streams

Builds the 4-tier stream hierarchy. Each stream tile shows live progress through three phases:

1. ⏳ **Creating stream...**
2. ⏳ **Stream created (id N) — adding project K of M: PROJ-KEY...**
3. ✓ **Stream id N · K project(s) added** (final summary, status flips to **Created**)

Individual Create buttons are disabled while any stream is in flight, so the consultant can't accidentally trigger parallel writes when CB's own toast says "Stream Created Successfully" (it's only the POST that's done — projects are still being added).

#### Stream creation policy (B-6)

CB's stream-inheritance model would pull all 100+ pre-existing projects from the Initial Stream into every new stream branched from it. To avoid that:

| Tier | Stream POST `sourceStreamId` | Per-project PUT `sourceStreamId` |
|---|---|---|
| **Library** | none (top-level) | each library project → initial stream |
| **PL** | none (top-level) | library project → its library stream; PL-specific project → initial stream |
| **Transform** | parent PL stream | none (pure mirror via inheritance) |
| **Release** | parent Transform stream | release-specific project → initial stream |

This per-project source mapping carries Library → PL lineage at the project level (visible in CB UI's Source Stream column) without polluting streams with unrelated initial-stream content. Result: a Chassis Library stream contains exactly its 2 chassis projects, not the entire CB instance.

### Step 4 — Summary

Overview of what was created, with per-tier stream listing and a **Cleanup panel** for end-of-demo housekeeping.

#### Cleanup panel

Two-step, scoped to the current run's category:

1. Click **Preview cleanup** — calls the dry-run endpoints, shows you the count of projects (deletable) and streams (matching this run's prefix; not deletable — CB v3 has no stream delete).
2. Click **Delete N project(s)** — confirms via native dialog, then calls the live delete.

Streams accumulate across runs. The session-prefix lets you identify them in CB UI for manual hide via `isHidden:true`.

---

## Configuration reference

All configuration lives in `.env` or shell environment.

| Variable | Required | Default | Description |
|---|---|---|---|
| `CB_URL` | Yes | — | Codebeamer base URL — host only, no `/cb` suffix (e.g., `https://host:9443`) |
| `CB_USER` | Yes | — | Codebeamer username |
| `CB_PASS` | Yes | — | Codebeamer password |
| `OPENAI_API_KEY` | Yes\* | — | OpenAI key for GPT-4o. \*Optional if you paste a key in the UI per-session |
| `CB_VERIFY_SSL` | No | `false` | Set `true` only if CB has a valid SSL cert |
| `PORT` | No | `5000` | Server port |
| `HOST` | No | `127.0.0.1` | Server bind address — keep on localhost |
| `FLASK_DEBUG` | No | `false` | Set `true` for local dev (auto-reload). Always leave `false` for demos. |

The wizard's **OpenAI API Key** field on Step 0 lets a consultant paste their own key for the session. The frontend sends it as `X-OpenAI-Key` request header; the backend uses the header value over the env-var. Useful when running on a shared machine without rotating env vars.

---

## Security model

- **SSRF protection**: only allowlisted CB paths are forwardable. Arbitrary URLs cannot be proxied. See `CB_V1_ALLOWED` and `CB_V3_ALLOWED` in [server.py](server.py).
- **OpenAI model allowlist**: only `gpt-4o`, `gpt-4o-mini`, and `gpt-4-turbo` are permitted. Token cap 16,384.
- **Localhost binding**: server binds to `127.0.0.1` by default — the OS user is the auth boundary.
- **Credentials server-side**: all secrets in `.env` (gitignored). Frontend never sees CB password.
- **Configurable SSL verification**: self-signed certs supported via `CB_VERIFY_SSL=false`.
- **Logs sanitized**: response-body logging is capped at 60KB and lives in `logs/` (gitignored).

---

## File map

### Active

| File | Role |
|---|---|
| [server.py](server.py) | Flask backend — proxies, allowlists, .env loader, log rotation, cleanup endpoints |
| [cb_demo.html](cb_demo.html) | Single-file React 18 + Babel-standalone wizard. No build step. |
| [.env](.env) | Local credentials (gitignored — create yours from the template above) |
| [.gitignore](.gitignore) | Excludes .env, logs/, __pycache__/, etc. |

### Archive

| Path | Why archived |
|---|---|
| [archive/](archive/) | Earlier 3-layer architecture (browser-only React + Anthropic API + downloadable Python script). Superseded by the current Flask + React design. See [archive/README.md](archive/README.md). |

### Documentation

| File | Description |
|---|---|
| [README.md](README.md) | This file |
| [ADR-001_MR_Stream_Architecture_Codebeamer_Evaluation.md](ADR-001_MR_Stream_Architecture_Codebeamer_Evaluation.md) | Architecture decision record for MR stream design |
| [Codebeamer Demo Generator Summary.txt](Codebeamer%20Demo%20Generator%20Summary.txt) | Original architecture and design notes |
| [CB_Demo_Generator_Code_Review.md](CB_Demo_Generator_Code_Review.md) | **[SUPERSEDED]** Reviews the old `.jsx` artifact in archive/ |
| [CB_Demo_Generator_Improvement_Plan.md](CB_Demo_Generator_Improvement_Plan.md) | **[SUPERSEDED]** Same scope as code review |

---

## Troubleshooting

**`OPENAI_API_KEY not set (no env var and no key supplied in UI)`**
Either set `OPENAI_API_KEY` in `.env` and restart, or paste a key in the wizard's Step 0 OpenAI section.

**`OpenAI response was truncated (finish_reason=length)`**
The schema you generated exceeds 16384 tokens. Reduce the number of release products (slider on Step 0) or pick a less complex domain template.

**`JSON repair failed`**
The error message will include `finish_reason` and a preview of the raw response. Most often this means OpenAI returned non-JSON (markdown fences slipped through, etc.). Click Generate again — output varies between runs at temperature 0.3.

**`Common ID duplicated in Stream` toast in CB UI**
Should not happen with the current B-6 stream policy. If you see it, you're running an old cached version of `cb_demo.html` — hard-refresh the browser (Ctrl+Shift+R or DevTools → "Empty Cache and Hard Reload").

**SSL errors on CB**
Self-signed certs are common on portal sandboxes. Keep `CB_VERIFY_SSL=false`.

**Port 5000 already in use**
```bash
# Windows
taskkill //F //IM python.exe
# Or set a different port
PORT=8080 python server.py
```

**Blank wizard / React not rendering**
Open DevTools (F12) → Console. Most likely a CDN load error (React, ReactDOM, or Babel from cdnjs.cloudflare.com is blocked).

**Streams pile up in CB after multiple runs**
CB v3 doesn't allow stream deletion via API. Use the Step 4 Cleanup panel to *list* streams matching this run's prefix — then hide them manually in CB UI (`isHidden:true`). The session-prefix on every stream name makes them easy to find.

---

## Codebeamer API endpoints used

| Endpoint | Method | Purpose |
|---|---|---|
| `/cb/rest/project` | POST | Create project |
| `/cb/rest/project/{id}` | DELETE | Delete project (cleanup) |
| `/cb/rest/projects/page/{n}` | GET | List projects (idempotency check, cleanup scan) |
| `/cb/api/projects/category` | POST | Create project category |
| `/cb/api/v3/projects/{id}/trackers` | GET | List trackers for a project |
| `/cb/api/v3/trackers/{id}/items` | POST | Create requirement / test case |
| `/cb/api/v3/trackers/{id}/schema` | GET | Discover field IDs (Verifies field) |
| `/cb/api/v3/items/{id}/fields` | PUT | Set field values (Verifies traceability) |
| `/cb/api/v3/streams/initial` | GET | Get initial stream id |
| `/cb/api/v3/streams/{id}/descendants` | GET | List streams under initial (cleanup) |
| `/cb/api/v3/streams/stream` | POST | Create stream |
| `/cb/api/v3/streams/{id}/projects` | PUT | Add project to stream with `sourceStreamId` + `addAllTrackers` |

---

## Versioning

This is the v4 baseline — Flask + React + .env + 4-tier stream policy + cleanup. Earlier 3-layer (browser-only) attempts are in [archive/](archive/).
