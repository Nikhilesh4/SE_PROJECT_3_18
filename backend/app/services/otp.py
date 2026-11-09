"""Email one-time codes used to verify an address before an account is created.

Codes live in Redis (hashed, short TTL, limited attempts). A successful check
returns a signed, short-lived token that /auth/register requires; the token
carries no `sub`, so it can never be used as a login token.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from jose import JWTError, jwt

from app.config import settings
from app.services.redis_cache import redis_cache

OTP_TTL_SECONDS = 10 * 60
RESEND_COOLDOWN_SECONDS = 60
MAX_ATTEMPTS = 5
VERIFIED_TOKEN_MINUTES = 30
_PURPOSE = "email_verified"


class OTPError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _code_key(email: str) -> str:
    return f"otp:{email}"


def _cooldown_key(email: str) -> str:
    return f"otp_cd:{email}"


def _digest(email: str, code: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), f"{email}:{code}".encode(), hashlib.sha256).hexdigest()


def issue_code(email: str) -> str:
    """Create and store a fresh 6-digit code for `email`; raises OTPError when throttled or Redis is down."""
    email = normalize_email(email)
    if redis_cache.get(_cooldown_key(email)) is not None:
        raise OTPError("Please wait a minute before requesting another code.", 429)

    code = f"{secrets.randbelow(1_000_000):06d}"
    stored = redis_cache.set(_code_key(email), {"hash": _digest(email, code), "attempts": 0}, OTP_TTL_SECONDS)
    if not stored:
        raise OTPError("Verification is temporarily unavailable. Please try again shortly.", 503)
    redis_cache.set(_cooldown_key(email), 1, RESEND_COOLDOWN_SECONDS)
    return code


def check_code(email: str, code: str) -> str:
    """Validate a code and return a verification token for `email`."""
    email = normalize_email(email)
    entry = redis_cache.get(_code_key(email))
    if not entry:
        raise OTPError("That code has expired. Request a new one.", 400)

    attempts = int(entry.get("attempts", 0))
    if attempts >= MAX_ATTEMPTS:
        redis_cache.delete(_code_key(email))
        raise OTPError("Too many wrong attempts. Request a new code.", 429)

    if not hmac.compare_digest(entry.get("hash", ""), _digest(email, code.strip())):
        entry["attempts"] = attempts + 1
        redis_cache.set(_code_key(email), entry, OTP_TTL_SECONDS)
        raise OTPError("That code is not correct.", 400)

    redis_cache.delete(_code_key(email))
    redis_cache.delete(_cooldown_key(email))
    return create_verification_token(email)


def create_verification_token(email: str) -> str:
    claims = {
        "purpose": _PURPOSE,
        "email": normalize_email(email),
        "exp": datetime.utcnow() + timedelta(minutes=VERIFIED_TOKEN_MINUTES),
    }
    return jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def token_matches_email(token: str | None, email: str) -> bool:
    if not token:
        return False
    try:
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return False
    return claims.get("purpose") == _PURPOSE and claims.get("email") == normalize_email(email)
