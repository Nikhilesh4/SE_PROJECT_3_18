"""
Ingestion Worker — periodically fetches all opportunities via AggregatorFacade,
deduplicates by source URL, and upserts into PostgreSQL.

Runs as an asyncio task registered in the FastAPI lifespan.  Each cycle:
1. Calls ``AggregatorFacade.fetch_all_opportunities()`` (RSS + Adzuna + Jooble).
2. The facade already deduplicates by URL.
3. Upserts into the ``rss_items`` table via ``RssItemRepository`` (dedup by guid).
4. Logs ingestion stats.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.db import SessionLocal
from app.repositories.rss_repository import RssItemRepository
from app.services.adapters.aggregator_facade import AggregatorFacade

logger = logging.getLogger("workers.ingestion")

# How often the full ingestion cycle runs (seconds).
INGESTION_INTERVAL_SECONDS = 30 * 60  # 30 minutes


async def _run_ingestion_cycle() -> dict:
    """
    Single ingestion cycle:
    1. Fetch all opportunities via the AggregatorFacade.
    2. Upsert into PostgreSQL (dedup by guid handled by the repository).
    3. Return stats dict.
    """
    facade = AggregatorFacade()

    # The facade is synchronous (uses httpx sync client under the hood),
    # so run in a thread to avoid blocking the event loop.
    loop = asyncio.get_running_loop()
    items = await loop.run_in_executor(None, facade.fetch_all_opportunities)

    if not items:
        logger.info("Ingestion cycle: no items fetched — nothing to persist.")
        return {"fetched": 0, "upserted": 0}

    # Persist to PostgreSQL
    db = SessionLocal()
    try:
        repo = RssItemRepository(db)
        upserted = repo.upsert_items(items)
    finally:
        db.close()

    logger.info(
        "Ingestion cycle complete: fetched=%d, upserted=%d",
        len(items),
        upserted,
    )
    return {"fetched": len(items), "upserted": upserted}


async def ingestion_loop() -> None:
    """
    Main loop — runs forever, executing full ingestion on a fixed interval.

    On startup it performs one immediate ingestion, then sleeps for
    ``INGESTION_INTERVAL_SECONDS`` between subsequent cycles.
    """
    logger.info(
        "Ingestion worker started (interval=%ds)", INGESTION_INTERVAL_SECONDS
    )

    # Initial ingestion on startup
    try:
        stats = await _run_ingestion_cycle()
        logger.info("Initial ingestion: %s", stats)
    except Exception as exc:
        logger.error("Initial ingestion failed: %s", exc)

    # Periodic loop
    while True:
        await asyncio.sleep(INGESTION_INTERVAL_SECONDS)
        try:
            stats = await _run_ingestion_cycle()
            logger.info("Periodic ingestion: %s", stats)
        except Exception as exc:
            logger.error("Periodic ingestion failed: %s", exc)


async def trigger_manual_ingestion() -> dict:
    """Trigger an immediate full ingestion cycle (used by admin endpoints)."""
    stats = await _run_ingestion_cycle()
    return {
        "ingested_at": datetime.now(timezone.utc).isoformat() + "Z",
        **stats,
    }
