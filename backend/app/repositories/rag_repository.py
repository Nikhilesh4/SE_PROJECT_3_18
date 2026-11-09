"""Data access for RAG passages (Repository pattern)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Sequence

from sqlalchemy import and_, delete, exists, func, or_, select
from sqlalchemy.orm import Session

from app.models.rag_chunk import RagChunk
from app.models.rss_item import RssItem

# Same rule as RssCacheService._is_active_item: a future deadline, or no
# deadline and seen within the last 45 days.
ACTIVE_WINDOW_DAYS = 45


@dataclass
class ChunkFilter:
    item_ids: Sequence[int] | None = None
    category: str | None = None
    active_only: bool = False


class RagRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    # ── Write ───────────────────────────────────────────────────────
    def replace_chunks(
        self, item_id: int, heading: str, passages: list[tuple[str, list[float]]]
    ) -> None:
        self._db.execute(delete(RagChunk).where(RagChunk.rss_item_id == item_id))
        self._db.add_all(
            RagChunk(
                rss_item_id=item_id,
                chunk_index=i,
                heading=heading,
                content=content,
                embedding=vector,
            )
            for i, (content, vector) in enumerate(passages)
        )

    def commit(self) -> None:
        self._db.commit()

    def items_without_chunks(self, limit: int) -> Sequence[RssItem]:
        """Embedded postings that have no passages yet (backfill and new rows)."""
        has_chunks = exists().where(RagChunk.rss_item_id == RssItem.id)
        return (
            self._db.query(RssItem)
            .filter(RssItem.embedding.isnot(None), ~has_chunks)
            .order_by(RssItem.id)
            .limit(limit)
            .all()
        )

    # ── Read ────────────────────────────────────────────────────────
    def keyword_search(
        self, query: str, filters: ChunkFilter, limit: int
    ) -> list[tuple[RagChunk, float]]:
        """Full-text search; `websearch_to_tsquery` accepts quotes, OR and -exclusions."""
        tsquery = func.websearch_to_tsquery("english", query)
        rank = func.ts_rank_cd(RagChunk.tsv, tsquery)
        stmt = (
            select(RagChunk, rank)
            .where(RagChunk.tsv.op("@@")(tsquery))
            .order_by(rank.desc(), RagChunk.id)
            .limit(limit)
        )
        return [(c, float(r)) for c, r in self._db.execute(self._filtered(stmt, filters))]

    def vector_search(
        self, vector: list[float], filters: ChunkFilter, limit: int
    ) -> list[tuple[RagChunk, float]]:
        """Nearest passages by cosine similarity (1 - distance)."""
        distance = RagChunk.embedding.cosine_distance(vector)
        stmt = select(RagChunk, distance).order_by(distance, RagChunk.id).limit(limit)
        return [(c, 1.0 - float(d)) for c, d in self._db.execute(self._filtered(stmt, filters))]

    def chunks_for_items(self, item_ids: Sequence[int]) -> list[RagChunk]:
        return (
            self._db.query(RagChunk)
            .filter(RagChunk.rss_item_id.in_(item_ids))
            .order_by(RagChunk.rss_item_id, RagChunk.chunk_index)
            .all()
        )

    def items_by_id(self, item_ids: Sequence[int]) -> dict[int, RssItem]:
        rows = self._db.query(RssItem).filter(RssItem.id.in_(list(item_ids))).all()
        return {r.id: r for r in rows}

    @staticmethod
    def _filtered(stmt, filters: ChunkFilter):
        if filters.item_ids is not None:
            stmt = stmt.where(RagChunk.rss_item_id.in_(filters.item_ids))
        # Searches across postings never surface QA-flagged ones; a search scoped to given ids may.
        cross_posting = filters.item_ids is None
        if filters.category or filters.active_only or cross_posting:
            stmt = stmt.join(RssItem, RssItem.id == RagChunk.rss_item_id)
        if cross_posting:
            stmt = stmt.where(RssItem.visible())
        if filters.category:
            stmt = stmt.where(RssItem.category == filters.category)
        if filters.active_only:
            now = datetime.now(timezone.utc)
            seen = func.coalesce(RssItem.published_at, RssItem.updated_at, RssItem.created_at)
            stmt = stmt.where(
                or_(
                    RssItem.application_deadline >= now,
                    and_(
                        RssItem.application_deadline.is_(None),
                        seen >= now - timedelta(days=ACTIVE_WINDOW_DAYS),
                    ),
                )
            )
        return stmt
