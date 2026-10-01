"""Configuration and path helpers for the steam-profile skill."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / "cache"
OUTPUT_DIR = ROOT / "output"
TEMPLATES_DIR = ROOT / "templates"
FONTS_DIR = ROOT / "fonts"

DEFAULT_CONFIG: Dict[str, Any] = {
    "steam_id": "",
    "default_mode": "lifetime",
    "top_games": 5,
    "max_categories": 8,
    "aggregation": "weighted",
    "scale": "sqrt",
    "metadata_source": "steamspy",
    "include_other": True,
    "cache_ttl_hours": 168,
}


def _load_dotenv() -> None:
    """Load ROOT/.env if present. Uses python-dotenv when available."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(env_path)
        return
    except ImportError:
        pass
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_config(path: str | os.PathLike[str] | None = None) -> Dict[str, Any]:
    """Return config.json merged over defaults, then overridden by env vars."""
    _load_dotenv()
    config = dict(DEFAULT_CONFIG)
    config_path = Path(path) if path else ROOT / "config.json"
    if config_path.exists():
        try:
            loaded = json.loads(config_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                config.update({k: v for k, v in loaded.items() if k in DEFAULT_CONFIG})
        except (json.JSONDecodeError, OSError):
            pass

    if os.environ.get("STEAM_ID"):
        config["steam_id"] = os.environ["STEAM_ID"]
    if os.environ.get("STEAM_MODE"):
        config["default_mode"] = os.environ["STEAM_MODE"]
    return config


def get_api_key(explicit: str | None = None) -> str:
    _load_dotenv()
    return explicit or os.environ.get("STEAM_API_KEY", "")


def ensure_dirs() -> None:
    for directory in (CACHE_DIR, OUTPUT_DIR):
        directory.mkdir(parents=True, exist_ok=True)
