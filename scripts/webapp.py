"""Shared request logic used by both serve.py (local) and api/*.py (Vercel).

This module is intentionally free of matplotlib/Pillow imports so it can run in
a small serverless bundle.
"""
from __future__ import annotations

import os
import re
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple

from . import session
from .cache import make_cache
from .categorize import load_category_config
from .config import load_config
from .ratelimit import RateLimiter
from .steam_fetch import (
    InvalidSteamId,
    NoGames,
    PrivateProfile,
    SteamAPIError,
    SteamError,
)

STEAM_OPENID_ENDPOINT = "https://steamcommunity.com/openid/login"
STEAM_APIKEY_URL = "https://steamcommunity.com/dev/apikey"
CLAIMED_ID_RE = re.compile(r"/(\d{17})$")

MODE_VALUES = ("weighted", "full", "primary")
SCALE_VALUES = ("linear", "sqrt", "log")

_rate_limiter = None


def _get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(
            limit=int(os.environ.get("RATE_LIMIT", "10")),
            window_seconds=int(os.environ.get("RATE_WINDOW_SECONDS", "600")),
        )
    return _rate_limiter


def build_login_url(base_url: str) -> str:
    realm = base_url.rstrip("/") + "/"
    params = {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "checkid_setup",
        "openid.return_to": f"{realm}api/auth/callback",
        "openid.realm": realm,
        "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
    }
    return f"{STEAM_OPENID_ENDPOINT}?{urllib.parse.urlencode(params)}"


def verify_openid(query: Dict[str, str]) -> Optional[str]:
    payload = {k: v for k, v in query.items() if k.startswith("openid.")}
    payload["openid.mode"] = "check_authentication"
    data = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(
        STEAM_OPENID_ENDPOINT,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        body = response.read().decode("utf-8", "replace")
    if "is_valid:true" not in body:
        return None
    claimed = payload.get("openid.claimed_id", "")
    match = CLAIMED_ID_RE.search(claimed)
    return match.group(1) if match else None


def resolve_steam_id(params: Dict[str, str], cookie_header: Optional[str]) -> str:
    return (
        (params.get("steamid") or "").strip()
        or session.steam_id_from_cookie(cookie_header)
        or os.environ.get("STEAM_ID", "")
        or str(load_config().get("steam_id", ""))
    )


def _int(value: Optional[str], fallback: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback


def _truthy(value: Optional[str], default: bool = True) -> bool:
    if value is None:
        return default
    return value not in ("0", "false", "False", "off")


def build_profile_payload(
    params: Dict[str, str],
    cookie_header: Optional[str],
    api_key: str,
) -> Dict[str, Any]:
    from .build_profile import build_profile

    config = load_config()
    steam_id = resolve_steam_id(params, cookie_header)
    if not steam_id:
        raise InvalidSteamId("No SteamID provided.")

    aggregation = params.get("aggregation") or config["aggregation"]
    if aggregation not in MODE_VALUES:
        aggregation = config["aggregation"]
    scale = params.get("scale") or config["scale"]
    if scale not in SCALE_VALUES:
        scale = config["scale"]

    top_games = _int(params.get("top"), int(config["top_games"]))
    max_categories = _int(params.get("categories"), int(config["max_categories"]))
    include_other = _truthy(params.get("include_other"), bool(config["include_other"]))
    mode = params.get("mode") or config["default_mode"]
    metadata_source = params.get("metadata_source") or config["metadata_source"]

    cache_key = "|".join(
        [
            steam_id,
            mode,
            aggregation,
            scale,
            str(top_games),
            str(max_categories),
            str(include_other),
            metadata_source,
        ]
    )
    profile_cache = make_cache("profile", ttl_hours=1.0)
    cached = profile_cache.get(cache_key)
    if cached is not None:
        return cached

    profile = build_profile(
        steam_id=steam_id,
        mode=mode,
        top_games=top_games,
        max_categories=max_categories,
        aggregation=aggregation,
        scale=scale,
        include_other=include_other,
        api_key=api_key,
        metadata_source=metadata_source,
        offline=params.get("offline", "0") in ("1", "true", "True"),
        cache_ttl_hours=float(config["cache_ttl_hours"]),
    )
    profile_cache.set(cache_key, profile)
    return profile


def get_config_payload(cookie_header: Optional[str], api_key: str) -> Dict[str, Any]:
    category_config = load_category_config()
    config = load_config()
    return {
        "steam_id": session.steam_id_from_cookie(cookie_header)
        or os.environ.get("STEAM_ID", "")
        or str(config.get("steam_id", "")),
        "has_api_key": bool(api_key),
        "api_key_url": STEAM_APIKEY_URL,
        "colors": category_config.get("colors", {}),
        "labels": category_config.get("labels", {}),
        "defaults": {
            key: config[key]
            for key in (
                "aggregation",
                "scale",
                "top_games",
                "max_categories",
                "include_other",
            )
        },
    }


def check_rate_limit(identifier: str) -> Dict[str, Any]:
    return _get_rate_limiter().check(identifier)


def error_status(exc: Exception) -> Tuple[int, str]:
    if isinstance(exc, PrivateProfile):
        return 400, "private"
    if isinstance(exc, InvalidSteamId):
        return 400, "invalid_id"
    if isinstance(exc, NoGames):
        return 400, "no_games"
    if isinstance(exc, SteamAPIError):
        return 502, "steam"
    if isinstance(exc, SteamError):
        return 502, "steam"
    return 500, "error"
