from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _base import JsonHandler  # noqa: E402  (also puts project root on sys.path)

from scripts import webapp  # noqa: E402
from scripts.config import _load_dotenv, get_api_key  # noqa: E402


class handler(JsonHandler):
    def do_GET(self) -> None:  # noqa: N802
        _load_dotenv()
        payload = webapp.get_config_payload(self.headers.get("Cookie"), get_api_key())
        self._json(200, payload)
