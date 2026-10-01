from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _base import JsonHandler  # noqa: E402


class handler(JsonHandler):
    def do_GET(self) -> None:  # noqa: N802
        self._json(200, {"ok": True})
