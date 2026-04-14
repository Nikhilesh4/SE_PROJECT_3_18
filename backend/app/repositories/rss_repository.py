"""Data access layer for cached RSS items (Repository pattern)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Sequence

from sqlalchemy import func, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.rss_item import RssItem
from app.schemas.rss_item import NormalizedRssItem


class RssItemRepository:
    """Encapsulates all DB operations for the rss_items table."""

    def __init__(self, db: Session) -> None:
        self._db = db

    # ── Upsert ──────────────────────────────────────────────────────
    def upsert_items(self, items: list[NormalizedRssItem]) -> int:
        """
        Bulk upsert items by GUID.  Returns the number of rows affected.
        On conflict (duplicate guid) we update title, summary, updated_at
        but keep the original created_at so we know when we first saw it.
        """
        if not items:
            return 0

        # Deduplicate by guid within the batch — PostgreSQL's ON CONFLICT DO UPDATE
        # raises CardinalityViolation if the same constrained column value appears
        # more than once in a single INSERT statement.
        seen: dict[str, dict] = {}
        for item in items:
            key = item.guid or item.url
            seen[key] = {
                "guid": key,
                "title": item.title,
                "url": item.url,
                "summary": item.summary,
                "published_at": item.published_at,
                "application_deadline": item.application_deadline,
                "category": item.category,
                "source_name": item.source_name,
                "feed_url": item.feed_url,
                "tags": item.tags,
                "author": item.author,
            }
        rows = list(seen.values())

        stmt = pg_insert(RssItem).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["guid"],
            set_={
                "title": stmt.excluded.title,
                "summary": stmt.excluded.summary,
                "published_at": stmt.excluded.published_at,
                "application_deadline": stmt.excluded.application_deadline,
                "tags": stmt.excluded.tags,
                "author": stmt.excluded.author,
                "updated_at": func.now(),
            },
        )
        result = self._db.execute(stmt)
        self._db.commit()
        return result.rowcount  # type: ignore[return-value]

    # ── Read ────────────────────────────────────────────────────────
    def get_items(
        self,
        *,
        category: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[RssItem]:
        q = self._db.query(RssItem)
        if category:
            q = q.filter(RssItem.category == category)
        q = q.order_by(RssItem.published_at.desc().nullslast(), RssItem.created_at.desc())
        return q.offset(offset).limit(limit).all()

    def count_items(self, *, category: str | None = None) -> int:
        q = self._db.query(func.count(RssItem.id))
        if category:
            q = q.filter(RssItem.category == category)
        return q.scalar() or 0

    def get_categories(self) -> list[str]:
        rows = (
            self._db.query(RssItem.category)
            .distinct()
            .order_by(RssItem.category)
            .all()
        )
        return [r[0] for r in rows]

    # ── Cleanup ─────────────────────────────────────────────────────
    def purge_old_items(self, days: int = 30) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = self._db.execute(
            delete(RssItem).where(RssItem.updated_at < cutoff)
        )
        self._db.commit()
        return result.rowcount  # type: ignore[return-value]
