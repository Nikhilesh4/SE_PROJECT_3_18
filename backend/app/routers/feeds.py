"""HTTP API for cached RSS opportunities and feed-source metadata."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from app.schemas.rss_item import NormalizedRssItem, RssAggregationResponse
from app.services.rss.cache_service import cache_service
from app.services.redis_cache import redis_cache
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
        description="Optional filter: internship, hackathon, research, job, freelance.",
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

    Architecture:
        Cache-Aside Pattern — Redis key: feed:{category}:{active_only}:{limit}:{offset}
        TTL: 5 minutes (300 seconds)
        Invalidated by: ingestion worker after each successful batch.
    """
    resolved_limit = limit_per_feed if limit_per_feed is not None else limit

    # ── Cache-Aside: Build key and check Redis first ─────────────────────
    cache_key = f"feed:{category}:{active_only}:{resolved_limit}:{offset}"
    cached = redis_cache.get(cache_key)
    if cached is not None:
        # Cache HIT — deserialize and mark origin for the UI
        response = RssAggregationResponse(**cached)
        response.from_cache = True
        return response

    # ── Cache MISS: fetch from DB ─────────────────────────────────────────
    result = cache_service.get_cached_feed(
        category=category,
        limit=resolved_limit,
        offset=offset,
        active_only=active_only,
    )

    # ── Store in Redis with 5-minute TTL ─────────────────────────────────
    # Note: we serialise BEFORE setting from_cache so the flag is never
    # baked into Redis — each response is tagged dynamically at read time.
    redis_cache.set(cache_key, result.model_dump(mode="json"), ttl_seconds=300)
    result.from_cache = False   # DB fetch
    return result


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


@router.get("/rss/{item_id}", response_model=NormalizedRssItem)
def get_rss_item(item_id: str) -> NormalizedRssItem:
    """
    Fetch a single opportunity by its GUID or URL identifier.

    Architecture:
        Cache-Aside Pattern — Redis key: opportunity:{item_id}
        TTL: 30 minutes (1800 seconds)
        Rationale: Popular opportunities are viewed by many users; caching
        prevents a 'hotspot' on the database for frequently clicked items.
    """
    # ── Cache-Aside: Check Redis first ──────────────────────────────────
    cache_key = f"opportunity:{item_id}"
    cached = redis_cache.get(cache_key)
    if cached is not None:
        return NormalizedRssItem(**cached)

    # ── Cache MISS: search in DB via cache_service ──────────────────────
    result = cache_service.get_cached_feed(limit=500, offset=0, active_only=False)
    item = next(
        (i for i in result.items if (i.guid or i.url) == item_id),
        None,
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Opportunity not found.")

    # ── Store in Redis with 30-minute TTL ───────────────────────────────
    redis_cache.set(cache_key, item.model_dump(mode="json"), ttl_seconds=1800)

    return item


@router.post("/rss/refresh")
async def rss_manual_refresh(
    category: str | None = Query(
        None,
        description="Optional category to refresh; if omitted, refresh all.",
    ),
) -> dict:
    """Manually trigger background refresh on demand."""
    return await trigger_manual_refresh(category=category)
