"""Steam Web API client: identity resolution and owned-games fetching."""
from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

from .cache import JsonCache

STEAM_API_BASE = "https://api.steampowered.com"
STEAMID64_RE = re.compile(r"^7656119\d{10}$")


class SteamError(Exception):
    """Base class for Steam related failures."""


class InvalidSteamId(SteamError):
    pass


class PrivateProfile(SteamError):
    pass


class NoGames(SteamError):
    pass


class SteamAPIError(SteamError):
    pass


def minutes_to_hours(minutes: int | float) -> float:
    return round(float(minutes) / 60.0, 1)


class SteamClient:
    def __init__(
        self,
        api_key: str,
        cache: Optional[JsonCache] = None,
        timeout: int = 15,
        max_retries: int = 3,
    ):
        if not api_key:
            raise SteamAPIError("STEAM_API_KEY is not set.")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.cache = cache
        self.session = requests.Session()

    def _get(self, interface: str, method: str, version: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{STEAM_API_BASE}/{interface}/{method}/{version}/"
        query = {"key": self.api_key, **params, "format": "json"}
        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, params=query, timeout=self.timeout)
                if response.status_code == 429:
                    time.sleep(2 ** attempt)
                    continue
                if response.status_code in (401, 403):
                    raise SteamAPIError(
                        "Steam rejected the request. Check your API key and "
                        "profile visibility."
                    )
                response.raise_for_status()
                return response.json()
            except requests.RequestException as exc:  # network / HTTP errors
                last_error = exc
                time.sleep(2 ** attempt)
        raise SteamAPIError(f"Steam request failed after {self.max_retries} attempts: {last_error}")

    def resolve_vanity_url(self, vanity: str) -> str:
        payload = self._get(
            "ISteamUser", "ResolveVanityURL", "v1", {"vanityurl": vanity}
        )
        response = payload.get("response", {})
        if response.get("success") != 1 or not response.get("steamid"):
            raise InvalidSteamId(f"Could not resolve vanity name '{vanity}'.")
        return response["steamid"]

    def normalize_steam_id(self, raw: str) -> str:
        """Accept a SteamID64, a /profiles/ URL, or a /id/ vanity URL."""
        value = (raw or "").strip()
        if not value:
            raise InvalidSteamId("No SteamID provided.")
        if STEAMID64_RE.match(value):
            return value
        if value.isdigit() and len(value) == 17:
            return value
        if "steamcommunity.com" in value:
            parsed = urlparse(value if "://" in value else f"https://{value}")
            parts = [p for p in parsed.path.split("/") if p]
            if len(parts) >= 2 and parts[0] == "profiles":
                return parts[1]
            if len(parts) >= 2 and parts[0] == "id":
                return self.resolve_vanity_url(parts[1])
        if not value.isdigit():
            return self.resolve_vanity_url(value)
        raise InvalidSteamId(f"Could not interpret SteamID '{raw}'.")

    def get_player_summary(self, steamid: str) -> Dict[str, Any]:
        payload = self._get(
            "ISteamUser", "GetPlayerSummaries", "v2", {"steamids": steamid}
        )
        players = payload.get("response", {}).get("players", [])
        if not players:
            raise InvalidSteamId(f"No Steam profile found for '{steamid}'.")
        return players[0]

    def _get_owned_games_raw(self, steamid: str) -> List[Dict[str, Any]]:
        payload = self._get(
            "IPlayerService",
            "GetOwnedGames",
            "v1",
            {
                "steamid": steamid,
                "include_appinfo": 1,
                "include_played_free_games": 1,
                "skip_unvetted_apps": 0,
            },
        )
        return payload.get("response", {}).get("games", []) or []

    def fetch_library(self, steamid: str, offline: bool = False) -> List[Dict[str, Any]]:
        """Return a normalized list of owned games.

        Raises PrivateProfile when game details are hidden, NoGames when the
        library is genuinely empty.
        """
        raw: Optional[List[Dict[str, Any]]] = None
        if self.cache is not None:
            raw = self.cache.get(f"ownedgames-{steamid}")
        if raw is None:
            if offline:
                raise SteamAPIError("Offline mode but no cached library found.")
            raw = self._get_owned_games_raw(steamid)
            if self.cache is not None:
                self.cache.set(f"ownedgames-{steamid}", raw)

        if not raw:
            # Empty can mean private or genuinely empty; disambiguate.
            try:
                summary = self.get_player_summary(steamid)
            except SteamError:
                summary = {}
            if summary.get("communityvisibilitystate", 3) != 3:
                raise PrivateProfile(
                    "Your Steam game details appear to be private. Make your "
                    "game details public and try again."
                )
            raise NoGames("No playable games were found for this Steam profile.")

        games: List[Dict[str, Any]] = []
        for game in raw:
            if not game.get("appid"):
                continue
            games.append(
                {
                    "appid": int(game["appid"]),
                    "name": game.get("name") or f"App {game['appid']}",
                    "playtime_minutes": int(game.get("playtime_forever", 0) or 0),
                    "hours": minutes_to_hours(game.get("playtime_forever", 0) or 0),
                    "img_icon_url": game.get("img_icon_url", ""),
                }
            )
        games.sort(key=lambda g: g["hours"], reverse=True)
        return games
