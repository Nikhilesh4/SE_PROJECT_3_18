"""Request rate limiting (slowapi) for the endpoints worth brute-forcing.

Limits are read from settings on every request, so they can be changed (and
tested) without rebuilding the app. Counters live in memory by default; point
RATE_LIMIT_STORAGE_URI at Redis to share them across API processes.

Behind a reverse proxy every request shares the proxy's IP unless uvicorn runs
with --proxy-headers and --forwarded-allow-ips set to the proxy.
"""

from __future__ import annotations

import hashlib

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings


def client_key(request: Request) -> str:
    """Per user when a bearer token is sent (uploads), otherwise per client IP.

    Limited routes validate the token before the limiter runs, so a forged
    token can't be used to dodge the limit.
    """
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer ") and len(auth) > 7:
        return "token:" + hashlib.sha256(auth[7:].encode()).hexdigest()[:16]
    return get_remote_address(request)


limiter = Limiter(
    key_func=client_key,
    storage_uri=settings.RATE_LIMIT_STORAGE_URI,
    enabled=settings.RATE_LIMIT_ENABLED,
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    window = int(exc.limit.limit.get_expiry())
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please wait a bit and try again."},
        headers={"Retry-After": str(window)},
    )


def login_limit() -> str:
    return settings.LOGIN_RATE_LIMIT


def register_limit() -> str:
    return settings.REGISTER_RATE_LIMIT


def upload_limit() -> str:
    return settings.UPLOAD_RATE_LIMIT
