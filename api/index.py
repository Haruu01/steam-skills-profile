from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.webhandler import Handler  # noqa: E402


class handler(Handler):
    pass
