"""Fixed-window rate limiting backed by Upstash Redis (in-memory fallback)."""
from __future__ import annotations

import os
import time
from typing import Dict, Tuple

import requests

from .cache import UPSTASH_TOKEN_ENV, UPSTASH_URL_ENV, upstash_configured


class RateLimiter:
    def __init__(
        self,
        limit: int = 10,
        window_seconds: int = 600,
        namespace: str = "ratelimit",
        timeout: int = 8,
    ):
        self.limit = limit
        self.window_seconds = window_seconds
        self.namespace = namespace
        self.timeout = timeout
        self.base = os.environ.get(UPSTASH_URL_ENV, "").rstrip("/")
        self.token = os.environ.get(UPSTASH_TOKEN_ENV, "")
        self._memory: Dict[str, Tuple[int, float]] = {}

    def _key(self, identifier: str) -> str:
        return f"steam-profile:{self.namespace}:{identifier}"

    def check(self, identifier: str) -> dict:
        """Return {allowed, limit, remaining, reset, count}."""
        if upstash_configured():
            return self._check_upstash(identifier)
        return self._check_memory(identifier)

    def _check_upstash(self, identifier: str) -> dict:
        key = self._key(identifier)
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            response = requests.post(
                f"{self.base}/incr/{key}", headers=headers, timeout=self.timeout
            )
            response.raise_for_status()
            count = int(response.json().get("result", 0))
            if count == 1:
                requests.post(
                    f"{self.base}/expire/{key}/{self.window_seconds}",
                    headers=headers,
                    timeout=self.timeout,
                )
        except (requests.RequestException, ValueError):
            # Fail open: never block the app because the limiter is down.
            return {"allowed": True, "limit": self.limit, "remaining": self.limit,
                    "reset": int(time.time()) + self.window_seconds, "count": 0}
        return {
            "allowed": count <= self.limit,
            "limit": self.limit,
            "remaining": max(0, self.limit - count),
            "reset": int(time.time()) + self.window_seconds,
            "count": count,
        }

    def _check_memory(self, identifier: str) -> dict:
        now = time.time()
        count, reset = self._memory.get(identifier, (0, now + self.window_seconds))
        if now >= reset:
            count, reset = 0, now + self.window_seconds
        count += 1
        self._memory[identifier] = (count, reset)
        return {
            "allowed": count <= self.limit,
            "limit": self.limit,
            "remaining": max(0, self.limit - count),
            "reset": int(reset),
            "count": count,
        }


def client_ip(headers) -> str:
    """Best-effort client IP from proxy headers (falls back to a constant)."""
    forwarded = headers.get("x-forwarded-for") or headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real = headers.get("x-real-ip") or headers.get("X-Real-IP")
    return real.strip() if real else "local"
