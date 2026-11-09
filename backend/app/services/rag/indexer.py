"""Write side of RAG: keep each posting's passages in step with its text.

Two triggers, both run by the embedding worker:
  - `index_rows`: called by `embed_pending_items` for the postings it just
    (re-)embedded. The upsert resets a posting's vector only when its title,
    summary or tags change, so this also replaces stale passages.
  - `index_pending_items`: backfill for embedded postings with no passages
    (rows embedded before this table existed).
"""

from __future__ import annotations

import logging
from typing import Sequence

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.rss_item import RssItem
from app.repositories.rag_repository import RagRepository
from app.services.matching.embeddings import EmbeddingProvider, get_embedder
from app.services.rag.chunking import chunk_posting, clean_text

logger = logging.getLogger("rag.indexer")


def index_rows(db: Session, rows: Sequence[RssItem], embedder: EmbeddingProvider) -> int:
    """(Re)build passages for `rows` in one transaction. Returns passages written."""
    plan = []
    for row in rows:
        heading = clean_text(row.title)
        passages = chunk_posting(row.title, row.tags or [], row.summary or "")
        plan.append((row.id, heading, passages))

    texts = [f"{heading}. {p}" for _, heading, passages in plan for p in passages]
    if not texts:
        return 0
    vectors = iter(embedder.embed(texts))

    repo = RagRepository(db)
    for item_id, heading, passages in plan:
        repo.replace_chunks(item_id, heading, [(p, next(vectors)) for p in passages])
    repo.commit()
    return len(texts)


def index_pending_items(batch_size: int = 64, max_items: int = 2000) -> int:
    """Backfill passages for embedded postings that have none. Returns postings indexed."""
    embedder = get_embedder()
    if embedder is None:
        return 0

    done = 0
    db = SessionLocal()
    try:
        repo = RagRepository(db)
        while done < max_items:
            rows = repo.items_without_chunks(limit=batch_size)
            if not rows:
                break
            index_rows(db, rows, embedder)
            done += len(rows)
    finally:
        db.close()
    return done
