"""Signed-cookie sessions for the deployed web app (stateless)."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
from http.cookies import SimpleCookie
from typing import Optional

COOKIE_NAME = "sp_sid"
STEAMID_RE = re.compile(r"^\d{17}$")
DEV_SECRET = "dev-insecure-session-secret"


def _secret(secret: Optional[str] = None) -> bytes:
    value = secret or os.environ.get("SESSION_SECRET")
    if not value:
        if os.environ.get("VERCEL_ENV") == "production" or os.environ.get("ENV") == "production":
            raise RuntimeError("SESSION_SECRET must be set in production.")
        value = DEV_SECRET
    return value.encode("utf-8")


def sign(steam_id: str, secret: Optional[str] = None) -> str:
    digest = hmac.new(_secret(secret), steam_id.encode("utf-8"), hashlib.sha256)
    return f"{steam_id}.{digest.hexdigest()[:32]}"


def verify(token: Optional[str], secret: Optional[str] = None) -> Optional[str]:
    if not token or "." not in token:
        return None
    steam_id, _, signature = token.rpartition(".")
    if not STEAMID_RE.match(steam_id):
        return None
    expected = hmac.new(_secret(secret), steam_id.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    if hmac.compare_digest(signature, expected):
        return steam_id
    return None


def read_cookie(cookie_header: Optional[str], name: str = COOKIE_NAME) -> Optional[str]:
    if not cookie_header:
        return None
    jar = SimpleCookie()
    try:
        jar.load(cookie_header)
    except Exception:  # noqa: BLE001 - malformed cookie header
        return None
    morsel = jar.get(name)
    return morsel.value if morsel else None


def session_value(steam_id: str, secret: Optional[str] = None) -> str:
    return sign(steam_id, secret)


def steam_id_from_cookie(cookie_header: Optional[str], secret: Optional[str] = None) -> Optional[str]:
    return verify(read_cookie(cookie_header), secret)
