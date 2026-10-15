#!/usr/bin/env python
"""Local development server + web UI for the steam-profile skill.

Uses the same shared handler as the Vercel deployment (``scripts/webhandler.py``)
but runs on a plain ``http.server``, serving static files from ``public/`` and
using the filesystem cache (Upstash is used automatically when its env vars are
present).

Usage:
    python serve.py                # http://localhost:8000
    python serve.py --port 8080
"""
from __future__ import annotations

import argparse
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL_ROOT))

from scripts.webhandler import Handler  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the localhost dev server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"steam-profile app running at http://localhost:{args.port}/")
    print(f"Setup (API key / sign-in):        http://localhost:{args.port}/setup")
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
