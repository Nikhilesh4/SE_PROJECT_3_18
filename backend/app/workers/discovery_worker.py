"""Discovery worker: runs the multi-agent pipeline on a schedule.

Sources that need no credentials (ATS boards, HN, Devpost, curated programs)
run by default. The web-search agent runs per profile only when a search key
is configured, capped per user. Each run is traced in `agent_runs`.
"""

from __future__ import annotations

import asyncio
import logging

from app.config import settings
from app.db import SessionLocal
from app.models.profile import Profile
from app.services.adapters.base_adapter import OpportunityAdapter
from app.services.discovery import fetcher, pipeline, websearch
from app.services.redis_cache import redis_cache
from app.schemas.rss_item import NormalizedRssItem

logger = logging.getLogger("workers.discovery")

DISCOVERY_INTERVAL_SECONDS = 6 * 3600
WEB_PROFILES_PER_RUN = 5  # budget: at most this many profiles get a web search each cycle


class _Fixed(OpportunityAdapter):
    """Adapter wrapper for items already gathered (the web-search results)."""

    def __init__(self, items: list[NormalizedRssItem]) -> None:
        self._items = items

    def fetch_opportunities(self, **_) -> list[NormalizedRssItem]:
        return self._items


def run_discovery_cycle() -> dict:
    db = SessionLocal()
    try:
        adapters = pipeline.default_adapters()
        if websearch.available():
            items: list[NormalizedRssItem] = []
            for profile in db.query(Profile).order_by(Profile.updated_at.asc()).limit(WEB_PROFILES_PER_RUN).all():
                items += websearch.discover_for_profile(profile.parsed_skills or [], profile.parsed_interests or [])
            if items:
                adapters["web_search"] = _Fixed(items)
        summary = pipeline.run_discovery(db, adapters, link_checker=fetcher.link_is_alive)
    finally:
        db.close()
    if summary.get("upserted"):
        redis_cache.delete_pattern("feed:*")
    return summary


async def discovery_loop() -> None:
    logger.info("Discovery worker started (interval=%ds)", DISCOVERY_INTERVAL_SECONDS)
    await asyncio.sleep(90)  # let startup ingestion finish first
    while True:
        try:
            summary = await asyncio.to_thread(run_discovery_cycle)
            logger.info("Discovery cycle: %s", summary)
        except Exception:
            logger.exception("Discovery cycle failed")
        await asyncio.sleep(DISCOVERY_INTERVAL_SECONDS)
