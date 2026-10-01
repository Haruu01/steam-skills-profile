"""Orchestrate the pipeline: fetch -> metadata -> categorize -> aggregate."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import config
from .aggregate import aggregate
from .cache import make_cache
from .categorize import categorize_games, load_category_config, load_tag_mapping
from .metadata import MetadataProvider, prefetch_tags
from .steam_fetch import SteamClient, minutes_to_hours


def _looks_like_steamid(value: str) -> bool:
    return bool(re.match(r"^7656119\d{10}$", (value or "").strip()))


def load_fixture(path: str | Path) -> Tuple[List[Dict[str, Any]], Dict[int, List[str]]]:
    """Load a fixture library. Accepts raw Steam payloads or normalized ones."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and "response" in data:
        data = data["response"].get("games", [])
    if isinstance(data, dict) and "games" in data:
        data = data["games"]
    if not isinstance(data, list):
        raise ValueError("Fixture must be a list of games or a Steam payload.")

    games: List[Dict[str, Any]] = []
    tags_by_appid: Dict[int, List[str]] = {}
    for entry in data:
        appid = int(entry.get("appid", entry.get("id", 0)) or 0)
        if not appid:
            continue
        if "hours" in entry and entry.get("hours") is not None:
            hours = round(float(entry["hours"]), 1)
        else:
            hours = minutes_to_hours(entry.get("playtime_forever", 0) or 0)
        games.append(
            {
                "appid": appid,
                "name": entry.get("name") or f"App {appid}",
                "hours": hours,
                "playtime_minutes": int(entry.get("playtime_forever", hours * 60) or 0),
            }
        )
        if entry.get("tags"):
            tags_by_appid[appid] = [str(t) for t in entry["tags"]]
    games.sort(key=lambda g: g["hours"], reverse=True)
    return games, tags_by_appid


def build_profile(
    steam_id: str = "",
    mode: str = "lifetime",
    top_games: int = 5,
    max_categories: int = 8,
    aggregation: str = "weighted",
    scale: str = "sqrt",
    include_other: bool = True,
    api_key: str = "",
    metadata_source: str = "steamspy",
    offline: bool = False,
    fixture: Optional[str] = None,
    cache_ttl_hours: float = 168.0,
) -> Dict[str, Any]:
    category_config = load_category_config()
    mapping = load_tag_mapping()

    persona: Dict[str, Any] = {}
    fixture_tags: Dict[int, List[str]] = {}

    if fixture:
        games, fixture_tags = load_fixture(fixture)
        resolved_id = steam_id or "fixture"

        def tag_lookup(appid: int) -> List[str]:
            return fixture_tags.get(appid, [])

        metadata_used = "fixture"
    else:
        cache = make_cache("steam", ttl_hours=cache_ttl_hours)
        client = SteamClient(api_key=api_key, cache=cache)
        resolved_id = client.normalize_steam_id(steam_id)
        if not offline:
            try:
                persona = client.get_player_summary(resolved_id)
            except Exception:  # noqa: BLE001 - persona is cosmetic only
                persona = {}
        games = client.fetch_library(resolved_id, offline=offline)

        meta_cache = make_cache("metadata", ttl_hours=cache_ttl_hours)
        provider = MetadataProvider(
            source=metadata_source, cache=meta_cache, offline=offline
        )
        prefetched = prefetch_tags(provider, [g["appid"] for g in games])

        def tag_lookup(appid: int) -> List[str]:
            return prefetched.get(appid, [])

        metadata_used = metadata_source

    games = categorize_games(games, tag_lookup, mapping)

    result = aggregate(
        games,
        mode=aggregation,
        top_games=top_games,
        max_categories=max_categories,
        include_other=include_other,
        scale=scale,
        category_order=category_config.get("order", []),
    )

    profile: Dict[str, Any] = {
        "profile": {
            "steam_id": resolved_id,
            "persona_name": persona.get("personaname", ""),
            "avatar": persona.get("avatarfull", ""),
            "mode": mode,
            "aggregation": result["aggregation"],
            "scale": result["scale"],
            "metadata_source": metadata_used,
            "generated_at": datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
        },
        "categories": result["categories"],
        "category_hours": result["category_hours"],
        "top_games": result["top_games"],
        "stats": {
            "game_count": result["game_count"],
            "total_hours": result["total_hours"],
        },
        "games": [
            {
                "appid": g["appid"],
                "name": g["name"],
                "hours": g["hours"],
                "tags": g.get("tags", []),
                "categories": g.get("categories", []),
            }
            for g in games
        ],
    }
    return profile


def write_profile_json(profile: Dict[str, Any], path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
