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

import os, json, re, sys
from flask import Flask, request, jsonify, send_from_directory, Response
import requests
from requests.auth import HTTPBasicAuth

app = Flask(__name__, static_folder=".", static_url_path="")

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
    re.compile(r"^projects/\d+/trackers$"),
    re.compile(r"^trackers/\d+/items$"),
    re.compile(r"^trackers/\d+/schema$"),
    re.compile(r"^items/\d+/fields$"),
    re.compile(r"^streams/initial$"),
    re.compile(r"^streams/stream$"),
    re.compile(r"^streams/\d+/projects$"),
]

CB_V1_ALLOWED = [
    re.compile(r"^project$"),
    re.compile(r"^project/\d+$"),
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


# ── OpenAI proxy ─────────────────────────────────────────────────────────────
@app.route("/api/openai/generate", methods=["POST"])
def openai_generate():
    key = OPENAI_KEY()
    if not key:
        return jsonify({"error": "OPENAI_API_KEY not set"}), 400

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
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            },
            json=safe_payload,
            timeout=120,
        )
        return Response(resp.content, status=resp.status_code,
                        content_type=resp.headers.get("Content-Type", "application/json"))
    except requests.RequestException as e:
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
        r = requests.request(
            method=request.method,
            url=url,
            auth=auth,
            headers=headers,
            json=body,
            timeout=30,
            verify=verify,
        )
        return Response(r.content, status=r.status_code,
                        content_type=r.headers.get("Content-Type", "application/json"))
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 502


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

    try:
        body = request.get_json(silent=True) if request.method in ("POST", "PUT") else None
        r = requests.request(
            method=request.method,
            url=url,
            auth=auth,
            headers=headers,
            json=body,
            timeout=30,
            verify=verify,
        )
        return Response(r.content, status=r.status_code,
                        content_type=r.headers.get("Content-Type", "application/json"))
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 502


# ── Startup ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Suppress InsecureRequestWarning for self-signed CB certs
    if not CB_VERIFY():
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "127.0.0.1")
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
+--------------------------------------------------------------+
""")
    if not CB_URL():
        print("  WARNING: CB_URL not set. Set it before using the app.")
    if not OPENAI_KEY():
        print("  WARNING: OPENAI_API_KEY not set. AI generation won't work.")

    app.run(host=host, port=port, debug=True)
