from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _base import JsonHandler  # noqa: E402

from scripts import session, webapp  # noqa: E402


class handler(JsonHandler):
    def do_GET(self) -> None:  # noqa: N802
        try:
            steam_id = webapp.verify_openid(self.query)
        except Exception as exc:  # noqa: BLE001
            self._json(502, {"ok": False, "error": f"OpenID error: {exc}"})
            return
        if not steam_id:
            self._json(400, {"ok": False, "error": "Steam sign-in could not be verified."})
            return
        cookie = (
            f"{session.COOKIE_NAME}={session.session_value(steam_id)}; "
            "Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=2592000"
        )
        self._redirect("/", cookie=cookie)
