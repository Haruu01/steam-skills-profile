"""Map Steam tags to the configured categories. Pure, testable functions."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from . import config


def load_tag_mapping(path: Optional[str] = None) -> Dict[str, List[str]]:
    mapping_path = Path(path) if path else config.DATA_DIR / "tag_mapping.json"
    data = json.loads(mapping_path.read_text(encoding="utf-8"))
    return {str(cat): [str(tag) for tag in tags] for cat, tags in data.items()}


def load_category_config(path: Optional[str] = None) -> Dict[str, Any]:
    config_path = Path(path) if path else config.DATA_DIR / "categories.json"
    if not config_path.exists():
        return {"order": [], "labels": {}, "colors": {}}
    return json.loads(config_path.read_text(encoding="utf-8"))


def _normalize(value: str) -> str:
    return value.strip().casefold()


def build_tag_index(mapping: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Return {normalized tag: [categories in mapping order]}."""
    index: Dict[str, List[str]] = {}
    for category, tags in mapping.items():
        for tag in tags:
            index.setdefault(_normalize(tag), []).append(category)
    return index


def match_categories(tags: Iterable[str], mapping: Dict[str, List[str]]) -> List[str]:
    """Return the matched categories for a tag list, preserving mapping order."""
    index = build_tag_index(mapping)
    matched: List[str] = []
    for tag in tags:
        for category in index.get(_normalize(tag), []):
            if category not in matched:
                matched.append(category)
    return matched


def categorize_games(
    games: List[Dict[str, Any]],
    tag_lookup: Callable[[int], List[str]],
    mapping: Dict[str, List[str]],
) -> List[Dict[str, Any]]:
    """Attach ``tags`` and ``categories`` to each game (returns new dicts)."""
    result: List[Dict[str, Any]] = []
    for game in games:
        appid = int(game.get("appid", 0))
        if appid == 0:
            continue  # Steam Client / non-game entries
        tags = [str(t) for t in (tag_lookup(appid) or [])]
        enriched = dict(game)
        enriched["tags"] = tags
        enriched["categories"] = match_categories(tags, mapping) or ["Other"]
        result.append(enriched)
    return result
