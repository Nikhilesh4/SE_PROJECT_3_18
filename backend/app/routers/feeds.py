"""HTTP API for cached RSS opportunities and feed-source metadata."""

from datetime import datetime

from fastapi import APIRouter, Query

from app.schemas.rss_item import RssAggregationResponse
from app.services.rss.cache_service import cache_service
from app.workers.rss_refresh_worker import trigger_manual_refresh

router = APIRouter(prefix="/feeds", tags=["feeds"])


@router.get("/rss", response_model=RssAggregationResponse)
def list_rss_opportunities(
    limit: int = Query(
        50,
        ge=1,
        le=500,
        description="Maximum number of cached opportunities to return.",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Offset for pagination over cached opportunities.",
    ),
    category: str | None = Query(
        None,
        description="Optional filter: internship, hackathon, research, course, job, freelance.",
    ),
    active_only: bool = Query(
        True,
        description="If true, only opportunities with active deadline/recent info are returned.",
    ),
    # Backward compatibility with older frontend query name.
    limit_per_feed: int | None = Query(
        None,
        ge=1,
        le=500,
        description="Deprecated alias for limit.",
    ),
) -> RssAggregationResponse:
    """
    Read opportunities from the local DB cache.
    RSS network fetching is handled by the background refresh worker.
    """
    resolved_limit = limit_per_feed if limit_per_feed is not None else limit
    return cache_service.get_cached_feed(
        category=category,
        limit=resolved_limit,
        offset=offset,
        active_only=active_only,
    )


@router.get("/rss/summary")
def rss_sources_summary() -> dict:
    """Lightweight: which sources exist (no network I/O)."""
    from app.services.rss.feed_sources import FEED_SOURCES

    by_cat: dict[str, int] = {}
    for s in FEED_SOURCES:
        by_cat[s.category] = by_cat.get(s.category, 0) + 1
    return {
        "total_sources": len(FEED_SOURCES),
        "by_category": by_cat,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/rss/cache-status")
def rss_cache_status() -> dict:
    """Return refresh timestamps, staleness, and counts per category."""
    return cache_service.get_cache_status()


@router.post("/rss/refresh")
async def rss_manual_refresh(
    category: str | None = Query(
        None,
        description="Optional category to refresh; if omitted, refresh all.",
    ),
) -> dict:
    """Manually trigger background refresh on demand."""
    return await trigger_manual_refresh(category=category)
