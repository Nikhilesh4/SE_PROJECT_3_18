"""
Background worker that periodically refreshes RSS feeds into the database.

Runs as an asyncio task registered via FastAPI lifespan.  On each cycle it:
1. Checks which categories are stale (via Redis TTL timestamps).
2. Fetches only stale feeds from upstream.
3. Upserts normalized items into the rss_items table.
4. Marks the category as refreshed in Redis.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.services.rss.aggregator import ingest_feed_source
from app.services.rss.cache_service import cache_service
from app.services.rss.feed_sources import FEED_SOURCES
from app.services.rss.refresh_strategy import CATEGORY_TTL_MINUTES

logger = logging.getLogger("rss.worker")

# How often the worker wakes up to check for stale categories (seconds).
CHECK_INTERVAL_SECONDS = 60


async def _refresh_category(category: str) -> None:
    """Fetch all feeds for a single category and persist to DB."""
    sources = [s for s in FEED_SOURCES if s.category == category]
    if not sources:
        return

    all_items = []
    for src in sources:
        try:
            items, status = ingest_feed_source(src, limit=50)
            if status.ok:
                all_items.extend(items)
                logger.info(
                    "[OK]   %s → %d items", src.source_name, status.items_normalized
                )
            else:
                logger.warning(
                    "[SKIP] %s → %s", src.source_name, status.error
                )
        except Exception as e:
            logger.error("[ERR]  %s → %s", src.source_name, e)

    if all_items:
        count = cache_service.persist_items(all_items)
        logger.info(
            "Category '%s': upserted %d items (%d from feeds)",
            category,
            count,
            len(all_items),
        )

    cache_service.mark_refreshed(category)


async def rss_refresh_loop() -> None:
    """Main loop — runs forever, refreshing stale categories."""
    logger.info("RSS refresh worker started")

    # Initial full refresh on startup
    for category in CATEGORY_TTL_MINUTES:
        try:
            logger.info("Initial refresh: category '%s'", category)
            await _refresh_category(category)
        except Exception as e:
            logger.error("Initial refresh failed for '%s': %s", category, e)

    logger.info("Initial refresh complete — entering periodic check loop")

    # Periodic refresh loop
    while True:
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
        for category in CATEGORY_TTL_MINUTES:
            try:
                if cache_service.is_stale(category):
                    logger.info("Refreshing stale category '%s'", category)
                    await _refresh_category(category)
            except Exception as e:
                logger.error("Refresh failed for '%s': %s", category, e)


async def trigger_manual_refresh(category: str | None = None) -> dict:
    """
    Trigger an immediate refresh.  If category is given, refresh only that
    category; otherwise refresh all.
    """
    categories = [category] if category else list(CATEGORY_TTL_MINUTES.keys())
    results = {}
    for cat in categories:
        try:
            await _refresh_category(cat)
            results[cat] = "refreshed"
        except Exception as e:
            results[cat] = f"error: {e}"
    return {
        "refreshed_at": datetime.now(timezone.utc).isoformat() + "Z",
        "results": results,
    }
