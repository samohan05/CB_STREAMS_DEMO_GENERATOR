#!/usr/bin/env python3
"""
CB Demo Generator — Local Server
Flask backend that proxies OpenAI + Codebeamer API calls (solves CORS).
Reads credentials from environment variables.

Usage:
  set CB_URL=https://pp-260127042638.portal.ptc.io:9443
  set CB_USER=admin
  set CB_PASS=yourpassword
  set OPENAI_API_KEY=sk-...
  pip install flask requests --break-system-packages
  python server.py
"""

import os, json, re, sys, logging
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, Response
import requests
from requests.auth import HTTPBasicAuth


# ── .env loader ──────────────────────────────────────────────────────────────
# Load key=value pairs from a sibling .env file into os.environ, BEFORE the
# config lambdas read them. Shell env vars take precedence — values already
# set are not overridden, so a developer can `set CB_URL=...` for a one-off
# session without editing the file.
def _load_env_file():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path, encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
    except OSError:
        pass  # silent — server starts without .env if it can't be read


_load_env_file()


app = Flask(__name__, static_folder=".", static_url_path="")

# ── Logging setup ───────────────────────────────────────────────────────────
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Start with a server-start log
_current_log_file = None
_current_file_handler = None

logger = logging.getLogger("cb_demo")
logger.setLevel(logging.DEBUG)

# Console handler — always active
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s", datefmt="%H:%M:%S"))
logger.addHandler(console_handler)

LOG_FORMAT = logging.Formatter("%(asctime)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

def _rotate_log_file(session_label="server"):
    """Create a new timestamped log file and switch the file handler to it."""
    global _current_log_file, _current_file_handler

    # Close previous handler
    if _current_file_handler:
        logger.removeHandler(_current_file_handler)
        _current_file_handler.close()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"cb_demo_{session_label}_{timestamp}.log"
    filepath = os.path.join(LOG_DIR, filename)

    _current_file_handler = logging.FileHandler(filepath, mode="w", encoding="utf-8")
    _current_file_handler.setLevel(logging.DEBUG)
    _current_file_handler.setFormatter(LOG_FORMAT)
    logger.addHandler(_current_file_handler)
    _current_log_file = filepath

    logger.info(f"Log session started: {filename}")
    return filename

# Create initial log on server start
_rotate_log_file("startup")

def log_request(api_type, method, url, body=None):
    """Log outgoing request to CB/OpenAI."""
    msg = f">>> {api_type} {method} {url}"
    logger.info(msg)
    if _current_file_handler:
        _current_file_handler.flush()
    if body:
        try:
            logger.debug(f"    REQUEST BODY: {json.dumps(body, indent=2)}")
        except:
            logger.debug(f"    REQUEST BODY: {body}")
        if _current_file_handler:
            _current_file_handler.flush()

def log_response(api_type, method, url, status, body_text=""):
    """Log incoming response from CB/OpenAI."""
    logger.info(f"<<< {api_type} {method} {url} => {status}")
    if body_text:
        # OpenAI responses can be 30-50KB; CB responses are smaller.
        # Cap at 60KB so we capture full responses for diagnostics without bloating logs.
        cap = 60000
        truncated = body_text[:cap] + (f"... (truncated, full {len(body_text)} bytes)" if len(body_text) > cap else "")
        logger.debug(f"    RESPONSE BODY: {truncated}")
    if _current_file_handler:
        _current_file_handler.flush()

# ── Config from env ──────────────────────────────────────────────────────────
CB_URL       = lambda: os.environ.get("CB_URL", "").rstrip("/")
CB_USER      = lambda: os.environ.get("CB_USER", "")
CB_PASS      = lambda: os.environ.get("CB_PASS", "")
OPENAI_KEY   = lambda: os.environ.get("OPENAI_API_KEY", "")
CB_VERIFY    = lambda: os.environ.get("CB_VERIFY_SSL", "false").lower() in ("true", "1", "yes")

# ── Allowed OpenAI models and limits ─────────────────────────────────────────
ALLOWED_MODELS = {"gpt-4o", "gpt-4o-mini", "gpt-4-turbo"}
MAX_TOKENS_LIMIT = 16384

# ── Path allowlists for CB proxy (SSRF protection) ──────────────────────────
# Only these path patterns are forwarded to the CB instance
CB_V3_ALLOWED = [
    re.compile(r"^projects/category$"),
    re.compile(r"^projects/\d+/trackers$"),
    re.compile(r"^trackers/\d+/items$"),
    re.compile(r"^trackers/\d+/schema$"),
    re.compile(r"^items/\d+$"),
    re.compile(r"^items/\d+/fields$"),
    re.compile(r"^streams/initial$"),
    re.compile(r"^streams/stream$"),
    re.compile(r"^streams/\d+$"),
    re.compile(r"^streams/\d+/projects$"),
    re.compile(r"^streams/\d+/descendants$"),
]

CB_V1_ALLOWED = [
    re.compile(r"^project$"),
    re.compile(r"^project/\d+$"),
    re.compile(r"^project/category$"),
    re.compile(r"^project/category/\d+$"),
    re.compile(r"^projects/page/\d+$"),
]


def _is_path_allowed(path, allowlist):
    """Check if the requested path matches any allowed pattern."""
    clean = path.strip("/")
    return any(pattern.match(clean) for pattern in allowlist)


# ── Serve frontend ───────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(".", "cb_demo.html")


# ── Config endpoint (tells frontend what's configured) ───────────────────────
@app.route("/api/config")
def config():
    return jsonify({
        "cbUrl": CB_URL(),
        "cbUser": CB_USER(),
        "hasOpenaiKey": bool(OPENAI_KEY()),
        "hasCbPass": bool(CB_PASS()),
    })


# ── Log session management ──────────────────────────────────────────────────
@app.route("/api/log/new-session", methods=["POST"])
def new_log_session():
    """Start a new log file. Called by frontend on each Generate click."""
    payload = request.get_json(silent=True) or {}
    label = re.sub(r"[^a-zA-Z0-9_-]", "_", payload.get("label", "session"))[:50]
    filename = _rotate_log_file(label)
    logger.info(f"Domain: {payload.get('domain', 'N/A')}")
    logger.info(f"Mode: {payload.get('mode', 'N/A')}")
    logger.info(f"CB_URL: {CB_URL() or '(NOT SET)'}")
    logger.info(f"CB_USER: {CB_USER() or '(NOT SET)'}")
    return jsonify({"logFile": filename, "logDir": LOG_DIR})


# ── OpenAI proxy ─────────────────────────────────────────────────────────────
@app.route("/api/openai/generate", methods=["POST"])
def openai_generate():
    # Prefer user-supplied key from request header (X-OpenAI-Key) over env var.
    # This lets a consultant paste a personal key in the UI without restarting
    # the server. Header form keeps the key out of request bodies and CB logs.
    user_key = (request.headers.get("X-OpenAI-Key") or "").strip()
    key = user_key or OPENAI_KEY()
    if not key:
        return jsonify({"error": "OPENAI_API_KEY not set (no env var and no key supplied in UI)"}), 400

    payload = request.get_json(silent=True)
    if not payload or not isinstance(payload, dict):
        return jsonify({"error": "Invalid JSON payload"}), 400

    # Enforce model allowlist and token limits
    model = payload.get("model", "gpt-4o")
    if model not in ALLOWED_MODELS:
        return jsonify({"error": f"Model '{model}' not allowed. Use one of: {', '.join(sorted(ALLOWED_MODELS))}"}), 400

    max_tokens = min(int(payload.get("max_tokens", 8192)), MAX_TOKENS_LIMIT)

    safe_payload = {
        "model": model,
        "temperature": float(payload.get("temperature", 0.3)),
        "max_tokens": max_tokens,
        "messages": payload.get("messages", []),
    }

    try:
        openai_url = "https://api.openai.com/v1/chat/completions"
        log_request("OPENAI", "POST", openai_url, {"model": model, "max_tokens": max_tokens, "messages": f"[{len(safe_payload['messages'])} messages]"})
        resp = requests.post(
            openai_url,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            },
            json=safe_payload,
            timeout=120,
        )
        log_response("OPENAI", "POST", openai_url, resp.status_code, resp.text)
        return Response(resp.content, status=resp.status_code,
                        content_type=resp.headers.get("Content-Type", "application/json"))
    except requests.RequestException as e:
        logger.error(f"OPENAI ERROR: {e}")
        return jsonify({"error": str(e)}), 502


# ── CB /api/ proxy (non-versioned endpoints like /projects/category) ────────
@app.route("/api/cb/api/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def cb_api_proxy(path):
    base = CB_URL()
    if not base:
        return jsonify({"error": "CB_URL not set"}), 400

    # Only allow specific paths
    if path.strip("/") not in ("projects/category",):
        return jsonify({"error": f"Path not allowed: {path}"}), 403

    url = f"{base}/cb/api/{path}"
    auth = HTTPBasicAuth(CB_USER(), CB_PASS())
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    verify = CB_VERIFY()

    try:
        body = request.get_json(silent=True) if request.method in ("POST", "PUT") else None
        log_request("CB-API", request.method, url, body)
        r = requests.request(
            method=request.method,
            url=url,
            auth=auth,
            headers=headers,
            json=body,
            timeout=30,
            verify=verify,
        )
        log_response("CB-API", request.method, url, r.status_code, r.text)
        return Response(r.content, status=r.status_code,
                        content_type=r.headers.get("Content-Type", "application/json"))
    except requests.RequestException as e:
        logger.error(f"CB-API ERROR: {e}")
        return jsonify({"error": str(e)}), 502


# ── CB v3 API proxy ──────────────────────────────────────────────────────────
@app.route("/api/cb/v3/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def cb_v3_proxy(path):
    base = CB_URL()
    if not base:
        return jsonify({"error": "CB_URL not set"}), 400

    if not _is_path_allowed(path, CB_V3_ALLOWED):
        return jsonify({"error": f"Path not allowed: {path}"}), 403

    url = f"{base}/cb/api/v3/{path}"
    auth = HTTPBasicAuth(CB_USER(), CB_PASS())
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    verify = CB_VERIFY()

    try:
        body = request.get_json(silent=True) if request.method in ("POST", "PUT", "PATCH") else None
        log_request("CB-V3", request.method, url, body)
        r = requests.request(
            method=request.method,
            url=url,
            auth=auth,
            headers=headers,
            json=body,
            timeout=30,
            verify=verify,
        )
        log_response("CB-V3", request.method, url, r.status_code, r.text)
        return Response(r.content, status=r.status_code,
                        content_type=r.headers.get("Content-Type", "application/json"))
    except requests.RequestException as e:
        logger.error(f"CB-V3 ERROR: {e}")
        return jsonify({"error": str(e)}), 502


# ── Cleanup endpoint — list / delete demo projects in a category ─────────────
@app.route("/api/cleanup/projects", methods=["POST"])
def cleanup_projects():
    """List and optionally delete all projects in a given category.

    Body: {"category": "<name>", "dry_run": true/false}
    Response: {"category": "...", "dry_run": ..., "projects": [{id, name, deleted, error}]}

    Always lists first. Only deletes if dry_run is explicitly false.
    Per-project failures are captured in the response, not raised.
    """
    base = CB_URL()
    if not base:
        return jsonify({"error": "CB_URL not set"}), 400

    payload = request.get_json(silent=True) or {}
    category = (payload.get("category") or "").strip()
    dry_run = payload.get("dry_run", True)
    if not category:
        return jsonify({"error": "category is required"}), 400

    auth = HTTPBasicAuth(CB_USER(), CB_PASS())
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    verify = CB_VERIFY()

    # 1. List projects in the category
    list_url = f"{base}/cb/rest/projects/page/1"
    try:
        log_request("CB-V1", "GET", f"{list_url}?pagesize=500&category={category}")
        r = requests.get(
            list_url,
            auth=auth,
            headers=headers,
            params={"pagesize": 500, "category": category},
            timeout=30,
            verify=verify,
        )
        log_response("CB-V1", "GET", list_url, r.status_code, r.text)
        r.raise_for_status()
        listing = r.json()
    except requests.RequestException as e:
        logger.error(f"CLEANUP list failed: {e}")
        return jsonify({"error": f"Failed to list projects: {e}"}), 502

    raw_projects = listing.get("projects") if isinstance(listing, dict) else listing
    raw_projects = raw_projects or []
    targets = []
    for p in raw_projects:
        pid = p.get("id")
        if not pid and p.get("uri"):
            try:
                pid = int(str(p["uri"]).rstrip("/").rsplit("/", 1)[-1])
            except (ValueError, AttributeError):
                pid = None
        if pid:
            targets.append({"id": pid, "name": p.get("name", "")})

    logger.info(f"CLEANUP category='{category}' found {len(targets)} project(s), dry_run={dry_run}")

    # 2. Dry-run — return the list and stop
    if dry_run:
        return jsonify({
            "category": category,
            "dry_run": True,
            "count": len(targets),
            "projects": targets,
        })

    # 3. Live — delete each project, capture per-item failures
    results = []
    for t in targets:
        del_url = f"{base}/cb/rest/project/{t['id']}"
        try:
            log_request("CB-V1", "DELETE", del_url)
            dr = requests.delete(del_url, auth=auth, headers=headers, timeout=30, verify=verify)
            log_response("CB-V1", "DELETE", del_url, dr.status_code, dr.text)
            results.append({
                "id": t["id"],
                "name": t["name"],
                "deleted": 200 <= dr.status_code < 300,
                "status": dr.status_code,
                "error": None if dr.ok else dr.text[:500],
            })
        except requests.RequestException as e:
            logger.error(f"CLEANUP delete {t['id']} failed: {e}")
            results.append({"id": t["id"], "name": t["name"], "deleted": False, "error": str(e)})

    return jsonify({
        "category": category,
        "dry_run": False,
        "count": len(results),
        "projects": results,
    })


# ── List streams — read-only helper for residue cleanup ─────────────────────
@app.route("/api/cleanup/streams", methods=["GET"])
def cleanup_list_streams():
    """List streams in the CB instance, optionally filtered by name prefix.

    Query params:
      prefix - optional, filter streams whose name starts with "[<prefix>]"
               (matches the session-prefix convention emitted by the wizard)

    Read-only. CB v3 does not expose stream deletion, so this endpoint
    helps the consultant identify residue across runs for manual hide/cleanup.

    Response: {"count": N, "streams": [{id, name, sourceStreamId, color}]}
    """
    base = CB_URL()
    if not base:
        return jsonify({"error": "CB_URL not set"}), 400

    prefix = (request.args.get("prefix") or "").strip()
    auth = HTTPBasicAuth(CB_USER(), CB_PASS())
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    verify = CB_VERIFY()

    # 1. Find the initial stream
    init_url = f"{base}/cb/api/v3/streams/initial"
    try:
        log_request("CB-V3", "GET", init_url)
        ir = requests.get(init_url, auth=auth, headers=headers, timeout=30, verify=verify)
        log_response("CB-V3", "GET", init_url, ir.status_code, ir.text)
        ir.raise_for_status()
        init_data = ir.json()
        init_id = init_data if isinstance(init_data, int) else (init_data.get("id") or init_data.get("streamId"))
        if not init_id:
            return jsonify({"error": "Could not resolve initial stream id"}), 502
    except requests.RequestException as e:
        logger.error(f"LIST-STREAMS init lookup failed: {e}")
        return jsonify({"error": str(e)}), 502

    # 2. Walk descendants of initial
    desc_url = f"{base}/cb/api/v3/streams/{init_id}/descendants"
    try:
        log_request("CB-V3", "GET", desc_url)
        dr = requests.get(desc_url, auth=auth, headers=headers, timeout=30, verify=verify)
        log_response("CB-V3", "GET", desc_url, dr.status_code, dr.text)
        dr.raise_for_status()
        body = dr.json()
    except requests.RequestException as e:
        logger.error(f"LIST-STREAMS descendants failed: {e}")
        return jsonify({"error": str(e)}), 502

    raw = body.get("descendants") if isinstance(body, dict) else body
    raw = raw or []
    streams = []
    pfx_match = f"[{prefix}]" if prefix else None
    for s in raw:
        name = s.get("name", "")
        if pfx_match and not name.startswith(pfx_match):
            continue
        streams.append({
            "id": s.get("id"),
            "name": name,
            "sourceStreamId": s.get("sourceStreamId"),
            "color": s.get("color"),
        })

    logger.info(f"LIST-STREAMS prefix='{prefix or '(none)'}' returned {len(streams)} of {len(raw)}")
    return jsonify({"count": len(streams), "totalScanned": len(raw), "prefix": prefix, "streams": streams})


# ── CB v1 REST API proxy ─────────────────────────────────────────────────────
@app.route("/api/cb/v1/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def cb_v1_proxy(path):
    base = CB_URL()
    if not base:
        return jsonify({"error": "CB_URL not set"}), 400

    if not _is_path_allowed(path, CB_V1_ALLOWED):
        return jsonify({"error": f"Path not allowed: {path}"}), 403

    url = f"{base}/cb/rest/{path}"
    auth = HTTPBasicAuth(CB_USER(), CB_PASS())
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    verify = CB_VERIFY()
    # Forward query parameters (e.g., ?pagesize=50&category=...)
    params = dict(request.args)

    try:
        body = request.get_json(silent=True) if request.method in ("POST", "PUT") else None
        log_request("CB-V1", request.method, url + (f"?{request.query_string.decode()}" if request.query_string else ""), body)
        r = requests.request(
            method=request.method,
            url=url,
            auth=auth,
            headers=headers,
            json=body,
            params=params,
            timeout=30,
            verify=verify,
        )
        log_response("CB-V1", request.method, url, r.status_code, r.text)
        return Response(r.content, status=r.status_code,
                        content_type=r.headers.get("Content-Type", "application/json"))
    except requests.RequestException as e:
        logger.error(f"CB-V1 ERROR: {e}")
        return jsonify({"error": str(e)}), 502


# ── Startup ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Suppress InsecureRequestWarning for self-signed CB certs
    if not CB_VERIFY():
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    logger.info("=" * 60)
    logger.info(f"CB Demo Generator — Server starting")
    logger.info(f"Log dir: {LOG_DIR}")
    logger.info("=" * 60)

    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "127.0.0.1")
    # Demo profile defaults to debug=False to avoid auto-reload mid-demo.
    # Set FLASK_DEBUG=true (or 1/yes) for local development.
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() in ("true", "1", "yes")
    print(f"""
+--------------------------------------------------------------+
|  CB Demo Generator - Local Server                            |
+--------------------------------------------------------------+
|  Open: http://{host}:{port}                            |
+--------------------------------------------------------------+
|  CB_URL:         {CB_URL() or '(NOT SET)':42}|
|  CB_USER:        {CB_USER() or '(NOT SET)':42}|
|  CB_PASS:        {'set' if CB_PASS() else '(NOT SET)':42}|
|  OPENAI_KEY:     {'set' if OPENAI_KEY() else '(NOT SET)':42}|
|  CB_VERIFY_SSL:  {str(CB_VERIFY()):42}|
|  FLASK_DEBUG:    {str(debug_mode):42}|
|  LOG_DIR:        {LOG_DIR:42}|
+--------------------------------------------------------------+
""")
    if not CB_URL():
        print("  WARNING: CB_URL not set. Set it before using the app.")
    if not OPENAI_KEY():
        print("  WARNING: OPENAI_API_KEY not set. AI generation won't work.")
    if debug_mode:
        print("  WARNING: FLASK_DEBUG=true — auto-reload is on. Disable for customer demos.")

    app.run(host=host, port=port, debug=debug_mode)
