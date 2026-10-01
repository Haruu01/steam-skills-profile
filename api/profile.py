from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _base import JsonHandler  # noqa: E402  (also puts project root on sys.path)

from scripts import webapp  # noqa: E402
from scripts.config import _load_dotenv, get_api_key  # noqa: E402
from scripts.ratelimit import client_ip  # noqa: E402


class handler(JsonHandler):
    def do_GET(self) -> None:  # noqa: N802
        _load_dotenv()
        rate = webapp.check_rate_limit(client_ip(self.headers))
        if not rate["allowed"]:
            self._json(
                429,
                {
                    "ok": False,
                    "code": "rate_limited",
                    "error": "Too many requests. Please try again later.",
                    "reset": rate["reset"],
                },
            )
            return
        try:
            profile = webapp.build_profile_payload(
                self.query, self.headers.get("Cookie"), get_api_key()
            )
        except Exception as exc:  # noqa: BLE001 - mapped to a friendly response
            status, code = webapp.error_status(exc)
            self._json(status, {"ok": False, "code": code, "error": str(exc)})
            return
        self._json(200, {"ok": True, "profile": profile, "rate": rate})
