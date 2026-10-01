"""Game metadata / tag lookup with caching and manual overrides."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import requests

from . import config
from .cache import JsonCache
from .steam_fetch import SteamAPIError

STEAMSPY_URL = "https://steamspy.com/api.php"
STORE_URL = "https://store.steampowered.com/api/appdetails"


def load_tag_overrides(path: Optional[str] = None) -> Dict[str, List[str]]:
    from pathlib import Path

    overrides_path = Path(path) if path else config.DATA_DIR / "manual_overrides.json"
    if not overrides_path.exists():
        return {}
    try:
        data = json.loads(overrides_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {
        str(k): list(v)
        for k, v in data.items()
        if not str(k).startswith("_") and isinstance(v, list)
    }


class MetadataProvider:
    """Resolves tags for an appid from SteamSpy, with a store fallback."""

    def __init__(
        self,
        source: str = "steamspy",
        cache: Optional[JsonCache] = None,
        offline: bool = False,
        timeout: int = 15,
        max_retries: int = 3,
    ):
        self.source = source
        self.cache = cache
        self.offline = offline
        self.timeout = timeout
        self.max_retries = max_retries
        self.overrides = load_tag_overrides()

    def get_tags(self, appid: int) -> List[str]:
        appid_str = str(appid)
        if appid_str in self.overrides:
            return list(self.overrides[appid_str])

        cache_key = f"tags-{self.source}-{appid_str}"
        if self.cache is not None:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return list(cached)
        if self.offline:
            return []

        tags = self._fetch_tags(appid)
        if self.cache is not None and tags is not None:
            self.cache.set(cache_key, tags)
        return tags or []

    def _fetch_tags(self, appid: int) -> Optional[List[str]]:
        if self.source == "steamspy":
            tags = self._from_steamspy(appid)
            if tags:
                return tags
        return self._from_store(appid)

    def _from_steamspy(self, appid: int) -> List[str]:
        payload = self._request(
            STEAMSPY_URL, {"request": "appdetails", "appid": appid}
        )
        if not isinstance(payload, dict):
            return []
        raw_tags = payload.get("tags")
        if isinstance(raw_tags, dict):
            # Sort by vote count descending for stable, meaningful ordering.
            ordered = sorted(raw_tags.items(), key=lambda kv: kv[1], reverse=True)
            return [str(tag) for tag, _ in ordered]
        if isinstance(raw_tags, list):
            return [str(tag) for tag in raw_tags]
        return []

    def _from_store(self, appid: int) -> List[str]:
        payload = self._request(STORE_URL, {"appids": appid, "l": "en"})
        try:
            entry = payload[str(appid)]
            if not entry.get("success"):
                return []
            data = entry.get("data", {})
        except (KeyError, AttributeError, TypeError):
            return []
        tags: List[str] = []
        for genre in data.get("genres", []) or []:
            if genre.get("description"):
                tags.append(genre["description"])
        for category in data.get("categories", []) or []:
            if category.get("description"):
                tags.append(category["description"])
        return tags

    def _request(self, url: str, params: Dict[str, Any]) -> Any:
        import time

        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                response = requests.get(url, params=params, timeout=self.timeout)
                if response.status_code == 429:
                    time.sleep(2 ** attempt)
                    continue
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                time.sleep(2 ** attempt)
        if last_error is not None:
            # Metadata failures must not break the pipeline.
            return []
        return []


def prefetch_tags(
    provider: "MetadataProvider",
    appids: List[int],
    max_workers: int = 8,
) -> Dict[int, List[str]]:
    """Fetch tags for many appids concurrently.

    Upstash/HTTP calls are IO bound, so a thread pool cuts first-run latency
    from minutes to seconds for large libraries.
    """
    from concurrent.futures import ThreadPoolExecutor

    unique = list(dict.fromkeys(appids))
    if not unique:
        return {}
    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
        results = executor.map(provider.get_tags, unique)
        return {appid: tags for appid, tags in zip(unique, results)}
