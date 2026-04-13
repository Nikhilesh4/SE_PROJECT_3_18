"""HTTP API: RSS feeds with database caching and background refresh."""

from datetime import datetime

from fastapi import APIRouter, Query

from app.schemas.rss_item import RssAggregationResponse
from app.services.rss.cache_service import cache_service
from app.workers.rss_refresh_worker import trigger_manual_refresh

router = APIRouter(prefix="/feeds", tags=["feeds"])


@router.get("/rss", response_model=RssAggregationResponse)
def list_rss_opportunities(
    limit_per_feed: int | None = Query(
        50,
        ge=1,
        le=500,
        description="Max total items to return (paginated).",
    ),
    offset: int = Query(0, ge=0, description="Pagination offset."),
    category: str | None = Query(
        None,
        description="Optional filter: internship, hackathon, research, course, job, freelance.",
    ),
) -> RssAggregationResponse:
    """
    Return cached RSS items from the database.
    Background worker keeps the data fresh; this endpoint is instant.
    """
    return cache_service.get_cached_feed(
        category=category,
        limit=limit_per_feed or 50,
        offset=offset,
    )


@router.post("/rss/refresh")
async def refresh_feeds(
    category: str | None = Query(
        None, description="Refresh a specific category, or all if omitted."
    ),
) -> dict:
    """Trigger an immediate refresh of RSS feeds (admin use)."""
    return await trigger_manual_refresh(category=category)


@router.get("/rss/cache-status")
def rss_cache_status() -> dict:
    """Show per-category cache freshness and item counts."""
    return cache_service.get_cache_status()


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
