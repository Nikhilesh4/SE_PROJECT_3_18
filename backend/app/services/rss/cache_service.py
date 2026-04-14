"""
RssCacheService — Singleton that mediates between the RSS aggregator, the
database (RssItemRepository), and Redis TTL timestamps.

API endpoints read from this service instead of hitting RSS feeds directly.
The background worker writes through this service after each refresh cycle.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Sequence

import redis

from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models.rss_item import RssItem
from app.repositories.rss_repository import RssItemRepository
from app.schemas.rss_item import (
    FeedSourceStatus,
    NormalizedRssItem,
    RssAggregationResponse,
)
from app.services.rss.refresh_strategy import CATEGORY_TTL_MINUTES, get_ttl_minutes

logger = logging.getLogger("rss.cache")

_REDIS_KEY_PREFIX = "rss:last_refresh:"


class RssCacheService:
    """Singleton-ish service (instantiated once in the module)."""

    def __init__(self) -> None:
        self._redis: redis.Redis | None = None

    # ── Redis connection (lazy) ─────────────────────────────────────
    def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(
                settings.REDIS_URL, decode_responses=True
            )
        return self._redis

    # ── Staleness checks ────────────────────────────────────────────
    def is_stale(self, category: str) -> bool:
        """Return True if the category needs a refresh."""
        r = self._get_redis()
        key = f"{_REDIS_KEY_PREFIX}{category}"
        last_ts = r.get(key)
        if last_ts is None:
            return True  # never refreshed
        try:
            last = datetime.fromisoformat(last_ts)
        except (TypeError, ValueError):
            return True
        ttl = get_ttl_minutes(category)
        age_minutes = (datetime.now(timezone.utc) - last).total_seconds() / 60
        return age_minutes >= ttl

    def mark_refreshed(self, category: str) -> None:
        r = self._get_redis()
        key = f"{_REDIS_KEY_PREFIX}{category}"
        r.set(key, datetime.now(timezone.utc).isoformat())

    # ── Read from DB ────────────────────────────────────────────────
    def get_cached_feed(
        self,
        *,
        category: str | None = None,
        limit: int = 50,
        offset: int = 0,
        active_only: bool = True,
    ) -> RssAggregationResponse:
        db = SessionLocal()
        try:
            repo = RssItemRepository(db)
            # Pull a bounded window from DB, then run active/deadline filtering in memory.
            # This keeps endpoint responses stable while preserving RSS-source flexibility.
            rows: Sequence[RssItem] = repo.get_items(category=category, limit=800, offset=0)
            if active_only:
                rows = [r for r in rows if self._is_active_item(r)]
            total = len(rows)
            rows = rows[offset : offset + limit]
            items = [self._row_to_schema(r) for r in rows]

            return RssAggregationResponse(
                items=items,
                sources=[],  # sources are a fetch-time concept
                total_items=total,
                fetched_at=datetime.now(timezone.utc),
            )
        finally:
            db.close()

    # ── Write to DB (called by the worker) ──────────────────────────
    def persist_items(self, items: list[NormalizedRssItem]) -> int:
        db = SessionLocal()
        try:
            repo = RssItemRepository(db)
            return repo.upsert_items(items)
        finally:
            db.close()

    # ── Cache status (observability) ────────────────────────────────
    def get_cache_status(self) -> dict:
        r = self._get_redis()
        db = SessionLocal()
        try:
            repo = RssItemRepository(db)
            categories = repo.get_categories()
            statuses = []
            for cat in categories:
                key = f"{_REDIS_KEY_PREFIX}{cat}"
                last_ts = r.get(key)
                stale = self.is_stale(cat)
                count = repo.count_items(category=cat)
                statuses.append(
                    {
                        "category": cat,
                        "last_refreshed": last_ts,
                        "is_stale": stale,
                        "ttl_minutes": get_ttl_minutes(cat),
                        "item_count": count,
                    }
                )
            # Also report categories that are configured but have no items yet
            for cat in CATEGORY_TTL_MINUTES:
                if cat not in categories:
                    key = f"{_REDIS_KEY_PREFIX}{cat}"
                    last_ts = r.get(key)
                    statuses.append(
                        {
                            "category": cat,
                            "last_refreshed": last_ts,
                            "is_stale": True,
                            "ttl_minutes": get_ttl_minutes(cat),
                            "item_count": 0,
                        }
                    )
            return {
                "categories": statuses,
                "total_items": repo.count_items(),
                "checked_at": datetime.now(timezone.utc).isoformat() + "Z",
            }
        finally:
            db.close()

    # ── Helpers ──────────────────────────────────────────────────────
    @staticmethod
    def _row_to_schema(row: RssItem) -> NormalizedRssItem:
        return NormalizedRssItem(
            title=row.title,
            url=row.url,
            summary=row.summary or "",
            published_at=row.published_at,
            application_deadline=row.application_deadline,
            category=row.category,
            source_name=row.source_name,
            feed_url=row.feed_url,
            tags=row.tags or [],
            author=row.author,
            guid=row.guid,
        )

    @staticmethod
    def _is_active_item(row: RssItem) -> bool:
        now = datetime.now(timezone.utc)
        if row.application_deadline is not None:
            return RssCacheService._as_utc(row.application_deadline) >= now

        # Per-category freshness cutoffs (no explicit deadline available).
        # Hackathons go stale quickly; other categories stay longer.
        cutoff_days = 14 if row.category == "hackathon" else 45
        recent_cutoff = now - timedelta(days=cutoff_days)
        if row.published_at is not None:
            return RssCacheService._as_utc(row.published_at) >= recent_cutoff
        if row.updated_at is not None:
            return RssCacheService._as_utc(row.updated_at) >= recent_cutoff
        return row.created_at is not None and RssCacheService._as_utc(row.created_at) >= recent_cutoff

    @staticmethod
    def _as_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)


# Module-level singleton
cache_service = RssCacheService()
