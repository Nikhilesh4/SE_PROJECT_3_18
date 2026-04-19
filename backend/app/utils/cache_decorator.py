"""
cache_decorator.py — Declarative caching via the @cached decorator.

Software Engineering Design:
-----------------------------
Pattern:  Decorator Pattern — Wraps a FastAPI route function with cache-aside
          logic without modifying the original function's code (Open-Closed Principle).

Pattern:  Cache-Aside — The decorator follows the exact Cache-Aside algorithm:
          1. Check the cache first (READ from Redis).
          2. On cache HIT: return the stored payload immediately (fast path).
          3. On cache MISS: call the original function, STORE the result in Redis,
             then return it.

Tactic:   Performance — Eliminates redundant DB queries and external API calls
          by serving repeated requests from in-memory Redis storage.
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from app.services.redis_cache import redis_cache

logger = logging.getLogger("unicompass.cache_decorator")


def cached(
    key_prefix: str,
    ttl_seconds: int,
    key_builder: Callable[..., str] | None = None,
) -> Callable:
    """
    Decorator that applies the Cache-Aside pattern to any function.

    The decorated function's result is stored in Redis under a computed key.
    On subsequent calls with the same arguments, the cached value is returned
    directly — skipping the function body entirely.

    Args:
        key_prefix:   Namespace prefix for the Redis key (e.g. "feed").
        ttl_seconds:  How long (in seconds) the cached value stays valid.
        key_builder:  Optional callable that receives (*args, **kwargs) and
                      returns the full Redis key string. If not provided, a
                      default key is built from key_prefix + all kwargs values.

    Usage::

        @cached(key_prefix="feed", ttl_seconds=300)
        def list_rss_opportunities(category=None, limit=50, offset=0, ...):
            ...

        @cached(
            key_prefix="profile",
            ttl_seconds=3600,
            key_builder=lambda *a, **kw: f"profile:{kw['user_id']}"
        )
        def get_my_profile(user_id: int, ...):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # ── Build the cache key ───────────────────────────────────
            if key_builder is not None:
                cache_key = key_builder(*args, **kwargs)
            else:
                # Default: join all kwarg values, skipping DB sessions and
                # SQLAlchemy objects (not serializable / not useful for keys).
                parts = []
                for k, v in sorted(kwargs.items()):
                    # Skip dependency-injected objects (db sessions, user objects)
                    if _is_dependency(v):
                        continue
                    parts.append(str(v))
                cache_key = f"{key_prefix}:{':'.join(parts)}" if parts else key_prefix

            # ── Cache-Aside: Check Redis first ────────────────────────
            cached_value = redis_cache.get(cache_key)
            if cached_value is not None:
                logger.debug("Cache HIT  key=%r", cache_key)
                return cached_value

            # ── Cache MISS: execute the real function ─────────────────
            logger.debug("Cache MISS key=%r", cache_key)
            result = func(*args, **kwargs)

            # ── Store result in Redis (only if serializable) ──────────
            if result is not None:
                # Pydantic models expose .model_dump() for JSON serialization
                if hasattr(result, "model_dump"):
                    storable = result.model_dump(mode="json")
                else:
                    storable = result

                redis_cache.set(cache_key, storable, ttl_seconds=ttl_seconds)

            return result

        # Attach metadata to the wrapper for introspection/testing
        wrapper._cache_key_prefix = key_prefix  # type: ignore[attr-defined]
        wrapper._cache_ttl = ttl_seconds  # type: ignore[attr-defined]
        return wrapper

    return decorator


def _is_dependency(value: Any) -> bool:
    """
    Return True for objects that should be excluded from cache key generation.

    FastAPI injects database sessions and User models as function arguments;
    these are runtime objects and must not become part of the cache key.
    """
    # Avoid importing heavy modules at the top of the file just for type checks
    type_name = type(value).__name__
    module = getattr(type(value), "__module__", "")

    return (
        "Session" in type_name          # SQLAlchemy Session
        or "User" in type_name          # Auth User model
        or "sqlalchemy" in module       # Any SQLAlchemy type
        or value is None
    )
