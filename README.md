# CB Demo Generator v4

AI-powered Codebeamer ALM demo provisioning tool. Generates realistic project structures, requirements, test cases, and stream hierarchies for Codebeamer demos using OpenAI GPT-4o.

![Architecture: Flask + React](https://img.shields.io/badge/Architecture-Flask_+_React-blue)
![Python 3.8+](https://img.shields.io/badge/Python-3.8+-green)
![License: Internal](https://img.shields.io/badge/License-Internal-yellow)

## Overview

CB Demo Generator v4 is a local web application that automates the creation of demo data in Codebeamer instances. It uses a 5-step wizard to walk you through generating and provisioning:

1. **Product Selection** — Choose from 8 pre-configured Philips product domains (MRI, Ultrasound, CT Scanner, etc.) or enter a custom domain.
2. **Projects** — AI generates projects grouped by category: Library (6 core), Product Line (1 per PL stream), and Release (1 per release stream). Each can be created individually or all at once.
3. **Requirements & Test Cases** — Creates 5 System Requirements + 2 Test Cases per project, with automatic Verifies traceability links between test cases and requirements.
4. **Streams** — Builds a 4-tier stream hierarchy (Library → Product Line → Transform → Release) with per-project source mapping and cascading selections.
5. **Summary** — Overview of everything created with next steps for the demo.

## Architecture

```
┌──────────────────┐         ┌──────────────────┐         ┌──────────────────┐
│                  │  HTTP   │                  │  HTTPS  │                  │
│  Browser (React) │ ──────► │  Flask Backend   │ ──────► │  Codebeamer API  │
│  cb_demo.html    │ :5000   │  server.py       │         │  (your instance) │
│                  │         │                  │         │                  │
│                  │         │         ┌────────┤         └──────────────────┘
│                  │         │         │ OpenAI │
│                  │         │         │ Proxy  │ ──────► api.openai.com
│                  │         │         └────────┤
└──────────────────┘         └──────────────────┘
```

The Flask backend acts as a proxy, solving CORS issues and keeping credentials server-side. The browser only talks to `localhost:5000`.

### API Routes

| Browser Request | Proxied To |
|---|---|
| `POST /api/openai/generate` | `https://api.openai.com/v1/chat/completions` |
| `GET/POST /api/cb/v3/{path}` | `{CB_URL}/cb/api/v3/{path}` |
| `GET/POST /api/cb/v1/{path}` | `{CB_URL}/cb/rest/{path}` |
| `GET /api/config` | Returns server configuration status |

## Prerequisites

- **Python 3.8+** with `pip`
- **OpenAI API Key** with access to GPT-4o (or GPT-4o-mini / GPT-4-turbo)
- **Codebeamer instance** with admin credentials (for project/stream creation)
- A modern web browser (Chrome, Edge, Firefox)

## Quick Start

### 1. Install dependencies

```bash
pip install flask requests
```

### 2. Set environment variables

**Windows (Command Prompt):**
```cmd
set CB_URL=https://your-codebeamer-instance:9443
set CB_USER=admin
set CB_PASS=yourpassword
set OPENAI_API_KEY=sk-your-openai-key
```

**Windows (PowerShell):**
```powershell
$env:CB_URL = "https://your-codebeamer-instance:9443"
$env:CB_USER = "admin"
$env:CB_PASS = "yourpassword"
$env:OPENAI_API_KEY = "sk-your-openai-key"
```

**macOS / Linux:**
```bash
export CB_URL=https://your-codebeamer-instance:9443
export CB_USER=admin
export CB_PASS=yourpassword
export OPENAI_API_KEY=sk-your-openai-key
```

### 3. Run the server

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
|  CB_URL:         https://your-instance:9443                  |
|  CB_USER:        admin                                       |
|  CB_PASS:        set                                         |
|  OPENAI_KEY:     set                                         |
|  CB_VERIFY_SSL:  False                                       |
+--------------------------------------------------------------+
```

### 4. Open in browser

```
http://localhost:5000
```

## Configuration

All configuration is done via environment variables:

| Variable | Required | Default | Description |
|---|---|---|---|
| `CB_URL` | Yes | — | Codebeamer instance URL (e.g., `https://host:9443`) |
| `CB_USER` | Yes | — | Codebeamer username |
| `CB_PASS` | Yes | — | Codebeamer password |
| `OPENAI_API_KEY` | Yes | — | OpenAI API key for GPT-4o |
| `CB_VERIFY_SSL` | No | `false` | Set to `true` to verify SSL certificates |
| `PORT` | No | `5000` | Server port |
| `HOST` | No | `127.0.0.1` | Server bind address |

The credentials pre-fill in the UI and can be edited per session without changing the environment variables.

## Usage Guide

### Dry Run Mode

The app starts in **Dry Run** mode by default (checkbox in the header). In this mode, all Create buttons simulate success without making any API calls. This lets you explore the full wizard flow safely before provisioning real data.

Uncheck the **Dry Run** checkbox to switch to **Live** mode for actual Codebeamer API writes.

### Step 1: Product Selection

Select one of the 8 pre-configured Philips product domains or enter a custom domain and industry. Verify the Codebeamer connection details (pre-filled from environment variables). Click **Generate** to have GPT-4o create the project structure.

The AI generates:
- 6 Library projects (core reusable components)
- 1 Product Line project per PL stream
- 1 Release project per release stream
- Requirements, test cases, and a 4-tier stream hierarchy for each

### Step 2: Projects

Review the AI-generated projects, organized by category (Library, Product Line, Release). You can edit project names and keys before creation. Use individual **Create** buttons or **Create All** for batch creation.

Projects are created using the Codebeamer v1 REST API (`POST /cb/rest/project`) with the default project template, which includes System Requirement Specification and Test Cases trackers.

### Step 3: Requirements & Test Cases

For each project, the app creates:
- 5 System Requirements in the System Requirement Specification tracker
- 2 Test Cases in the Test Cases tracker
- Traceability links: TC1 verifies requirements 1-3, TC2 verifies requirements 4-5

The **Verifies** field is dynamically discovered from the Test Cases tracker schema (not hardcoded), ensuring compatibility across different Codebeamer instances.

### Step 4: Streams

Build the 4-tier stream hierarchy:

| Tier | Description | Project Selection |
|---|---|---|
| **Library** | Base streams for reusable components | Fixed: 2 projects per library (auto-assigned) |
| **Product Line** | Feature branches for product lines | Selectable: pick from library projects + PL-specific project |
| **Transform** | Integration streams | Auto-mirrors Product Line selections |
| **Release** | Release branches | Mirrors Transform + optional release-specific projects |

Key behaviors:
- **Per-project source mapping**: Each project in a PL stream sources from the library stream it belongs to (not all from one library).
- **Cascading selections**: Changes to PL stream project selections automatically propagate to Transform and Release streams.
- **Release extras**: Release streams can include additional release-specific projects beyond what's mirrored from Transform.

### Step 5: Summary

Overview of all created artifacts with Codebeamer navigation tips for the demo.

## Security

The Flask backend includes several security measures:

- **SSRF Protection**: Only allowlisted API paths are forwarded to Codebeamer. Arbitrary URLs cannot be proxied.
- **OpenAI Model Allowlist**: Only `gpt-4o`, `gpt-4o-mini`, and `gpt-4-turbo` are permitted.
- **Token Limit Cap**: Maximum 16,384 tokens per OpenAI request.
- **Localhost Binding**: Server binds to `127.0.0.1` by default (not `0.0.0.0`).
- **Credentials Server-Side**: API keys and passwords are stored in environment variables, never sent from the browser to external services.
- **Configurable SSL Verification**: SSL cert verification for CB connections can be enabled via `CB_VERIFY_SSL=true`.

## Files

### Core Application

| File | Description |
|---|---|
| `server.py` | Flask backend — proxies OpenAI and Codebeamer API calls, serves the frontend |
| `cb_demo.html` | Frontend wizard UI — standalone React 18 app with Babel standalone for JSX |

### Supporting Files (Reference / Development)

| File | Description |
|---|---|
| `cb_demo_generator.jsx` | Original React artifact version (not used by the local app) |
| `cb_demo_MR.py` | Python-based MR demo builder script |
| `cb_demo_MR.txt` | MR demo configuration reference |
| `cb_api_validation.py` | CB API validation scripts (v1) |
| `cb_api_validation_v2.py` | CB API validation scripts (v2) |
| `cb_api_validation_v3.py` | CB API validation scripts (v3) |
| `helpers.js` | JavaScript helper utilities |
| `jsonParser.js` | AI JSON response parser |
| `prompt.js` | AI prompt templates |
| `templates.js` | Project templates |
| `pythonBuilder.js` | Python script builder |
| `cb_demo_core.js` | Core demo logic module |
| `cb_demo_core.test.js` | Test suite for core logic |
| `package.json` | Node.js package manifest |

### Documentation

| File | Description |
|---|---|
| `README.md` | This file |
| `ADR-001_MR_Stream_Architecture_Codebeamer_Evaluation.md` | Architecture decision record for MR stream design |
| `CB_Demo_Generator_Code_Review.md` | Code review findings and fixes |
| `CB_Demo_Generator_Improvement_Plan.md` | Future improvement roadmap |

## Troubleshooting

**"OPENAI_API_KEY not set"**
Make sure you set the environment variable in the same terminal session before running `python server.py`. Environment variables don't persist across terminal sessions.

**SSL errors when connecting to Codebeamer**
The server defaults to `CB_VERIFY_SSL=false` for self-signed certificates. If your instance uses a valid certificate, set `CB_VERIFY_SSL=true`.

**Port already in use**
Set a different port: `set PORT=8080` (Windows) or `export PORT=8080` (macOS/Linux), then restart the server.

**Blank page / React not rendering**
Open the browser's Developer Tools (F12 → Console) to check for JavaScript errors. Ensure your browser isn't blocking CDN scripts (React, ReactDOM, Babel are loaded from cdnjs.cloudflare.com).

**"Path not allowed" errors**
The backend only proxies specific Codebeamer API paths for security. If you need additional paths, update the `CB_V3_ALLOWED` or `CB_V1_ALLOWED` lists in `server.py`.

**AI generation produces invalid JSON**
The parser includes multiple fallback strategies (regex extraction, brace balancing, smart quote repair). If it still fails, try regenerating — GPT-4o output can vary between runs.

## Codebeamer API Reference

The app uses two Codebeamer API versions:

- **v3 API** (`/cb/api/v3/`) — Used for trackers, items, fields, schemas, and streams
- **v1 REST API** (`/cb/rest/`) — Used for project creation (v3 has no POST /projects endpoint)

Key endpoints used:

| Endpoint | Method | Purpose |
|---|---|---|
| `/cb/rest/project` | POST | Create a new project |
| `/cb/api/v3/projects/{id}/trackers` | GET | List trackers in a project |
| `/cb/api/v3/trackers/{id}/items` | POST | Create requirements and test cases |
| `/cb/api/v3/trackers/{id}/schema` | GET | Discover field IDs (e.g., Verifies) |
| `/cb/api/v3/items/{id}/fields` | PATCH | Update item fields (traceability links) |
| `/cb/api/v3/streams/initial` | POST | Create a library (initial) stream |
| `/cb/api/v3/streams/stream` | POST | Create PL/Transform/Release streams |
| `/cb/api/v3/streams/{id}/projects` | POST | Add projects to a stream |
