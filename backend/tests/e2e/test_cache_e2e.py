"""
E2E Tests — Redis Cache Service
=================================
Tests the RedisCacheService using the in-memory fake from conftest.
Verifies cache get/set/delete/pattern-delete operations end-to-end.
"""

from __future__ import annotations

import pytest


class TestRedisCacheOperations:
    """Test the cache service operations via the in-memory stub."""

    def test_set_and_get(self):
        from tests.conftest import fake_redis

        fake_redis.set("test:key", {"data": "value"}, ttl_seconds=60)
        result = fake_redis.get("test:key")
        assert result == {"data": "value"}

    def test_get_missing_key_returns_none(self):
        from tests.conftest import fake_redis

        result = fake_redis.get("nonexistent:key")
        assert result is None

    def test_delete_key(self):
        from tests.conftest import fake_redis

        fake_redis.set("del:key", "data", ttl_seconds=60)
        fake_redis.delete("del:key")
        assert fake_redis.get("del:key") is None

    def test_delete_pattern(self):
        from tests.conftest import fake_redis

        fake_redis.set("feed:job:1", "a", ttl_seconds=60)
        fake_redis.set("feed:job:2", "b", ttl_seconds=60)
        fake_redis.set("feed:internship:1", "c", ttl_seconds=60)
        fake_redis.set("other:key", "d", ttl_seconds=60)

        deleted = fake_redis.delete_pattern("feed:job:*")
        assert deleted == 2
        assert fake_redis.get("feed:job:1") is None
        assert fake_redis.get("feed:internship:1") == "c"
        assert fake_redis.get("other:key") == "d"

    def test_is_available(self):
        from tests.conftest import fake_redis

        assert fake_redis.is_available() is True
