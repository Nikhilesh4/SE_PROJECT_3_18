"""
RedisCacheService — Central caching service for the UniCompass application.

Software Engineering Design:
-----------------------------
Pattern:  Singleton — This module exposes a single shared `redis_cache` instance.
          The lazy-connection approach ensures Redis is only contacted when first needed.

Tactic:   Performance — Acts as the foundational layer for the Cache-Aside pattern
          used across all endpoints, reducing expensive DB and external API calls.

Tactic:   Availability — All Redis calls are wrapped in try/except so a Redis outage
          never crashes the application; methods gracefully return None/False on failure.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import redis

from app.config import settings

logger = logging.getLogger("unicompass.redis_cache")


class RedisCacheService:
    """
    Generic Redis caching helper.

    Provides get / set / delete / delete_pattern operations on a shared Redis
    connection.  All serialization is handled via JSON so callers work with
    plain Python dicts — no manual encoding/decoding needed.

    Singleton Pattern: Instantiated once at module level as `redis_cache`.
    """

    def __init__(self) -> None:
        # Lazy connection — not opened until first use
        self._client: redis.Redis | None = None

    # ── Connection (Lazy Initialization) ────────────────────────────────
    def _get_client(self) -> redis.Redis:
        """Return the shared Redis client, creating it on first call."""
        if self._client is None:
            self._client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
        return self._client

    # ── Core Cache Operations ────────────────────────────────────────────
    def get(self, key: str) -> Any | None:
        """
        Retrieve a cached value by key.

        Returns the deserialized Python object, or None if the key
        does not exist or Redis is unavailable.
        """
        try:
            raw = self._get_client().get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as exc:
            logger.warning("Redis GET failed for key=%r: %s", key, exc)
            return None

    def set(self, key: str, value: Any, ttl_seconds: int) -> bool:
        """
        Store a value in the cache with a TTL (Time-To-Live).

        Args:
            key:         The cache key string.
            value:       Any JSON-serializable Python object.
            ttl_seconds: Seconds until automatic expiry.

        Returns True on success, False if Redis is unavailable.
        """
        try:
            serialized = json.dumps(value, default=str)
            self._get_client().setex(key, ttl_seconds, serialized)
            logger.debug("Redis SET key=%r ttl=%ds", key, ttl_seconds)
            return True
        except Exception as exc:
            logger.warning("Redis SET failed for key=%r: %s", key, exc)
            return False

    def delete(self, key: str) -> bool:
        """
        Delete a specific key from the cache (cache invalidation).

        Returns True on success or if the key did not exist.
        """
        try:
            self._get_client().delete(key)
            logger.debug("Redis DEL key=%r", key)
            return True
        except Exception as exc:
            logger.warning("Redis DEL failed for key=%r: %s", key, exc)
            return False

    def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a glob-style pattern (bulk invalidation).

        Example: delete_pattern("feed:*") clears the entire feed cache.

        Returns the number of keys deleted.
        """
        try:
            client = self._get_client()
            keys = list(client.scan_iter(match=pattern, count=100))
            if keys:
                deleted = client.delete(*keys)
                logger.info(
                    "Redis bulk DEL pattern=%r → %d keys removed", pattern, deleted
                )
                return deleted
            return 0
        except Exception as exc:
            logger.warning(
                "Redis bulk DEL failed for pattern=%r: %s", pattern, exc
            )
            return 0

    def is_available(self) -> bool:
        """Ping Redis — returns True if the service is reachable."""
        try:
            return self._get_client().ping()
        except Exception:
            return False


# ── Module-level Singleton (used throughout the application) ────────────
redis_cache = RedisCacheService()
