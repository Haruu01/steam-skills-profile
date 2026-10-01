"""Aggregate per-game playtime into categories and top-games lists."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

OTHER = "Other"


def _normalize_value(value: float, maximum: float, scale: str) -> float:
    if maximum <= 0:
        return 0.0
    ratio = max(0.0, value) / maximum
    if scale == "sqrt":
        result = math.sqrt(ratio) * 100.0
    elif scale == "log":
        result = math.log1p(value) / math.log1p(maximum) * 100.0
    else:  # linear
        result = ratio * 100.0
    return round(result, 1)


def _raw_category_hours(
    games: List[Dict[str, Any]], mode: str, category_order: List[str]
) -> Dict[str, float]:
    totals: Dict[str, float] = {}
    for game in games:
        hours = float(game.get("hours", 0))
        categories = list(game.get("categories") or [OTHER])
        if not categories:
            categories = [OTHER]
        if mode == "full":
            for category in categories:
                totals[category] = totals.get(category, 0.0) + hours
        elif mode == "primary":
            primary = _pick_primary(categories, category_order)
            totals[primary] = totals.get(primary, 0.0) + hours
        else:  # weighted (default)
            share = hours / len(categories)
            for category in categories:
                totals[category] = totals.get(category, 0.0) + share
    return totals


def _pick_primary(categories: List[str], category_order: List[str]) -> str:
    for category in category_order:
        if category in categories and category != OTHER:
            return category
    return categories[0]


def aggregate(
    games: List[Dict[str, Any]],
    mode: str = "weighted",
    top_games: int = 5,
    max_categories: int = 8,
    include_other: bool = True,
    scale: str = "sqrt",
    category_order: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Return the deterministic profile payload used for rendering.

    ``categories`` holds normalized values (0-100); ``category_hours`` holds
    the raw aggregated hours so totals remain auditable.
    """
    category_order = category_order or []
    totals = _raw_category_hours(games, mode, category_order)

    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    selected = ranked[: max(1, max_categories)]
    remainder = ranked[max(1, max_categories):]

    if include_other and remainder:
        other_hours = sum(hours for _, hours in remainder)
        selected_hours = dict(selected)
        selected_hours[OTHER] = selected_hours.get(OTHER, 0.0) + other_hours
        selected = list(selected_hours.items())

    # Discard zero-value categories before rendering.
    selected = [(cat, hours) for cat, hours in selected if hours > 0]
    selected.sort(key=lambda kv: kv[1], reverse=True)

    maximum = max((hours for _, hours in selected), default=0.0)
    normalized = {
        category: _normalize_value(hours, maximum, scale)
        for category, hours in selected
    }

    ordered_top_games = sorted(
        (
            {"name": g.get("name", "Unknown"), "hours": round(float(g.get("hours", 0)), 1)}
            for g in games
        ),
        key=lambda g: g["hours"],
        reverse=True,
    )[: max(0, top_games)]

    return {
        "categories": normalized,
        "category_hours": {cat: round(hours, 1) for cat, hours in selected},
        "top_games": ordered_top_games,
        "aggregation": mode,
        "scale": scale,
        "total_hours": round(sum(float(g.get("hours", 0)) for g in games), 1),
        "game_count": len(games),
    }
