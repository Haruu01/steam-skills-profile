"""Cache backends: filesystem (local dev) and Upstash Redis (serverless).

The active backend is selected automatically: when UPSTASH_REDIS_REST_URL and
UPSTASH_REDIS_REST_TOKEN are set the Upstash backend is used, otherwise values
fall back to JSON files under ``cache/``.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Optional

import requests

from . import config

UPSTASH_URL_ENV = "UPSTASH_REDIS_REST_URL"
UPSTASH_TOKEN_ENV = "UPSTASH_REDIS_REST_TOKEN"


class BaseCache:
    def get(self, key: str) -> Optional[Any]:
        raise NotImplementedError

    def set(self, key: str, value: Any, ttl_seconds: Optional[float] = None) -> None:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        return None

    def get_or_set(
        self,
        key: str,
        producer: Callable[[], Any],
        ttl_seconds: Optional[float] = None,
    ) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = producer()
        if value is not None:
            self.set(key, value, ttl_seconds)
        return value


class NullCache(BaseCache):
    def get(self, key: str) -> Optional[Any]:
        return None

    def set(self, key: str, value: Any, ttl_seconds: Optional[float] = None) -> None:
        return None


class FilesystemCache(BaseCache):
    """TTL-aware JSON cache on disk. Used for local development."""

    def __init__(self, namespace: str, ttl_hours: float = 168.0, enabled: bool = True):
        self.namespace = namespace
        self.ttl_seconds = float(ttl_hours) * 3600.0
        self.enabled = enabled
        self.dir = config.CACHE_DIR / namespace
        if self.enabled:
            self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
        safe = "".join(c for c in key if c.isalnum() or c in "-_.")[:48]
        return self.dir / f"{safe}-{digest}.json"

    def get(self, key: str) -> Optional[Any]:
        if not self.enabled:
            return None
        path = self._path(key)
        if not path.exists():
            return None
        if self.ttl_seconds >= 0:
            age = time.time() - path.stat().st_mtime
            if age > self.ttl_seconds:
                return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def set(self, key: str, value: Any, ttl_seconds: Optional[float] = None) -> None:
        if not self.enabled:
            return
        path = self._path(key)
        try:
            path.write_text(
                json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError:
            pass

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink(missing_ok=True)
        except OSError:
            pass


class UpstashCache(BaseCache):
    """Redis-compatible cache over the Upstash REST API (works on serverless)."""

    def __init__(
        self,
        namespace: str,
        ttl_hours: float = 168.0,
        url: Optional[str] = None,
        token: Optional[str] = None,
        timeout: int = 10,
    ):
        self.base = (url or os.environ.get(UPSTASH_URL_ENV, "")).rstrip("/")
        self.token = token or os.environ.get(UPSTASH_TOKEN_ENV, "")
        self.namespace = namespace
        self.ttl_seconds = int(float(ttl_hours) * 3600.0)
        self.timeout = timeout

    def _key(self, key: str) -> str:
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
        return f"steam-profile:{self.namespace}:{digest}"

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def get(self, key: str) -> Optional[Any]:
        try:
            response = requests.get(
                f"{self.base}/get/{self._key(key)}",
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json().get("result")
        except (requests.RequestException, ValueError):
            return None
        if result is None:
            return None
        try:
            return json.loads(result)
        except (json.JSONDecodeError, TypeError):
            return None

    def set(self, key: str, value: Any, ttl_seconds: Optional[float] = None) -> None:
        ttl = int(ttl_seconds) if ttl_seconds is not None else self.ttl_seconds
        url = f"{self.base}/set/{self._key(key)}"
        if ttl and ttl > 0:
            url += f"?EX={ttl}"
        try:
            requests.post(
                url,
                headers={**self._headers(), "Content-Type": "application/json"},
                data=json.dumps(value, ensure_ascii=False).encode("utf-8"),
                timeout=self.timeout,
            )
        except requests.RequestException:
            pass

    def delete(self, key: str) -> None:
        try:
            requests.post(
                f"{self.base}/del/{self._key(key)}",
                headers=self._headers(),
                timeout=self.timeout,
            )
        except requests.RequestException:
            pass


def upstash_configured() -> bool:
    return bool(os.environ.get(UPSTASH_URL_ENV) and os.environ.get(UPSTASH_TOKEN_ENV))


def make_cache(
    namespace: str, ttl_hours: float = 168.0, enabled: bool = True
) -> BaseCache:
    if not enabled:
        return NullCache()
    if upstash_configured():
        return UpstashCache(namespace, ttl_hours=ttl_hours)
    return FilesystemCache(namespace, ttl_hours=ttl_hours, enabled=True)


# Backwards-compatible alias used by older imports.
JsonCache = FilesystemCache
