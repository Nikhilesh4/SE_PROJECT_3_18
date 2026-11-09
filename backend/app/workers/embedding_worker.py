"""
Embedding Worker — keeps opportunity and profile vectors up to date.

Runs as an asyncio task registered in the FastAPI lifespan.  It:
1. Loads the embedding model once in a thread (first run downloads ~90 MB).
2. Every cycle, embeds rows whose vector is NULL — new items from any
   ingestion worker, items whose text changed, and profiles — and splits
   those postings into RAG passages (plus a backfill for older rows).
3. Invalidates feed caches when vectors changed, since rankings shift.

Embedding is CPU-bound, so all model work runs in a thread to keep the
event loop responsive.
"""

from __future__ import annotations

import asyncio
import logging

from app.config import settings
from app.services.matching.embeddings import get_embedder
from app.services.matching.semantic import embed_pending_items, embed_pending_profiles
from app.services.rag.indexer import index_pending_items
from app.services.redis_cache import redis_cache

logger = logging.getLogger("workers.embedding")

# How often the worker looks for unembedded rows (seconds).
EMBED_INTERVAL_SECONDS = 60


def _run_embedding_cycle() -> dict:
    items = embed_pending_items()  # also (re)builds those postings' RAG passages
    profiles = embed_pending_profiles()
    backfilled = index_pending_items()
    if backfilled:
        logger.info("Indexed RAG passages for %d postings", backfilled)
    if items:
        invalidated = redis_cache.delete_pattern("feed:*")
        logger.info(
            "Embedded %d items, %d profiles; invalidated %d feed cache keys",
            items,
            profiles,
            invalidated,
        )
    elif profiles:
        logger.info("Embedded %d profiles", profiles)
    return {"items": items, "profiles": profiles, "rag_backfilled": backfilled}


async def embedding_loop() -> None:
    if not settings.EMBEDDINGS_ENABLED:
        logger.info("Embeddings disabled — semantic ranking off")
        return

    if await asyncio.to_thread(get_embedder) is None:
        return  # load failure already logged; keyword ranking stays active

    logger.info("Embedding worker started (interval=%ds)", EMBED_INTERVAL_SECONDS)
    while True:
        try:
            await asyncio.to_thread(_run_embedding_cycle)
        except Exception:
            logger.exception("Embedding cycle failed")
        await asyncio.sleep(EMBED_INTERVAL_SECONDS)
