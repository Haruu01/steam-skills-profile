from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _base import JsonHandler  # noqa: E402

from scripts import webapp  # noqa: E402


class handler(JsonHandler):
    def do_GET(self) -> None:  # noqa: N802
        self._redirect(webapp.build_login_url(self.base_url))
