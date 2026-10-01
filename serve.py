#!/usr/bin/env python
"""Local development server + web UI for the steam-profile skill.

Mirrors the production Vercel routes (api/*.py) but runs on a plain
http.server, serving static files from ``public/`` and using the filesystem
cache (Upstash is used automatically when its env vars are present).

Usage:
    python serve.py                # http://localhost:8000
    python serve.py --port 8080
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL_ROOT))

from scripts import session, webapp  # noqa: E402
from scripts.config import _load_dotenv, get_api_key  # noqa: E402
from scripts.ratelimit import client_ip  # noqa: E402

CONFIG_PATH = SKILL_ROOT / "config.json"
PUBLIC_DIR = SKILL_ROOT / "public"
STEAM_APIKEY_URL = webapp.STEAM_APIKEY_URL

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".json": "application/json; charset=utf-8",
}

SETUP_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>steam-profile &middot; setup</title>
<style>
  :root { color-scheme: dark; }
  body { margin:0; min-height:100vh; display:flex; align-items:center;
         justify-content:center; background:#0B1020; color:#F5F7FF;
         font:16px/1.5 system-ui,Segoe UI,sans-serif; }
  .card { width:min(560px,92vw); background:#141B36; border:1px solid #26304f;
          border-radius:18px; padding:36px 40px; box-shadow:0 24px 60px #0008; }
  h1 { font-size:26px; margin:0 0 4px; letter-spacing:.04em; }
  .sub { color:#9AA4C7; margin:0 0 26px; }
  a.btn { display:inline-block; padding:13px 22px; border-radius:10px;
          background:#1b2838; color:#fff; text-decoration:none; font-weight:600;
          border:1px solid #2a475e; }
  a.btn:hover { background:#2a475e; }
  .ok { color:#81C784; font-weight:600; }
  .warn { color:#FFB74D; }
  code { background:#0B1020; padding:2px 7px; border-radius:6px; color:#4FC3F7; }
  .row { margin:18px 0; }
  .muted { color:#9AA4C7; font-size:14px; }
</style></head><body><div class="card">{body}</div></body></html>"""


def read_config_file() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def setup_page(steam_id, api_key: str, message: str = "") -> bytes:
    key_status = '<span class="ok">detected</span>' if api_key else '<span class="warn">not set</span>'
    id_status = f'<span class="ok">{steam_id}</span>' if steam_id else '<span class="warn">unknown</span>'
    notice = f'<p class="muted">{message}</p>' if message else ""
    body = f"""
      <h1>STEAM PROFILE &middot; SETUP</h1>
      <p class="sub">Local development server</p>
      <div class="row">Steam API key: {key_status}</div>
      <div class="row">SteamID64: {id_status}</div>
      {notice}
      <div class="row">
        <a class="btn" href="/api/auth/login">Sign in through Steam</a>
        &nbsp;
        <a class="btn" href="{STEAM_APIKEY_URL}" target="_blank" rel="noopener">Get a Steam API key</a>
      </div>
      <p class="muted">Register the domain <code>localhost</code>, then set
      <code>STEAM_API_KEY</code> in <code>.env</code>.</p>
      <p class="row"><a class="btn" href="/">Open the app</a></p>
    """
    return SETUP_PAGE.replace("{body}", body).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "steam-profile-local/0.3"

    def _send(self, status: int, body: bytes, content_type: str = "text/html; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _redirect(self, location: str, cookie: str | None = None) -> None:
        self.send_response(302)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Location", location)
        self.end_headers()

    @property
    def _params(self) -> dict:
        parsed = urllib.parse.urlparse(self.path)
        return {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}

    @property
    def _base_url(self) -> str:
        return f"http://{self.headers.get('Host', 'localhost')}"

    def _serve_static(self, path: str) -> bool:
        relative = "index.html" if path in ("/", "") else path.lstrip("/")
        candidate = (PUBLIC_DIR / relative).resolve()
        if PUBLIC_DIR.resolve() not in candidate.parents and candidate != PUBLIC_DIR.resolve():
            self._send(403, b"forbidden", "text/plain")
            return True
        if not candidate.is_file():
            return False
        self._send(200, candidate.read_bytes(), CONTENT_TYPES.get(candidate.suffix, "application/octet-stream"))
        return True

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/health" or path == "/api/health":
            self._send(200, b"ok", "text/plain")
            return

        if path in ("/api/auth/login", "/login"):
            self._redirect(webapp.build_login_url(self._base_url))
            return

        if path in ("/api/auth/callback", "/callback"):
            _load_dotenv()
            try:
                steam_id = webapp.verify_openid(self._params)
            except Exception as exc:  # noqa: BLE001
                self._send(502, setup_page(None, "", f"OpenID error: {exc}"))
                return
            if not steam_id:
                self._send(400, setup_page(None, "", "Steam sign-in could not be verified."))
                return
            cookie = (
                f"{session.COOKIE_NAME}={session.session_value(steam_id)}; "
                "Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000"
            )
            self._redirect("/", cookie=cookie)
            return

        if path == "/setup":
            _load_dotenv()
            steam_id = read_config_file().get("steam_id") or webapp.resolve_steam_id({}, self.headers.get("Cookie"))
            self._send(200, setup_page(steam_id, get_api_key()))
            return

        if path == "/api/config":
            _load_dotenv()
            self._json(200, webapp.get_config_payload(self.headers.get("Cookie"), get_api_key()))
            return

        if path == "/api/profile":
            _load_dotenv()
            rate = webapp.check_rate_limit(client_ip(self.headers))
            if not rate["allowed"]:
                self._json(429, {"ok": False, "code": "rate_limited",
                                 "error": "Too many requests. Please try again later.",
                                 "reset": rate["reset"]})
                return
            try:
                profile = webapp.build_profile_payload(self._params, self.headers.get("Cookie"), get_api_key())
            except Exception as exc:  # noqa: BLE001
                status, code = webapp.error_status(exc)
                self._json(status, {"ok": False, "code": code, "error": str(exc)})
                return
            self._json(200, {"ok": True, "profile": profile, "rate": rate})
            return

        if not self._serve_static(path):
            self._send(404, b"not found", "text/plain")

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[serve] " + (fmt % args) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the localhost dev server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"steam-profile app running at http://localhost:{args.port}/")
    print(f"Setup (API key / sign-in):        http://localhost:{args.port}/setup")
    print(f"Register the domain 'localhost' at {STEAM_APIKEY_URL}")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
