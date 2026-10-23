"""HTTP API for cached RSS opportunities and feed-source metadata.

Architecture Patterns Used:
  - Cache-Aside Pattern: Redis sits in front of PostgreSQL.
  - Facade Pattern: Single entry point for all feed operations.
  - Strategy Pattern: FeedFetchStrategy (ABC) with HybridRelevanceFetchStrategy,
    RelevanceFetchStrategy and DefaultFetchStrategy, selected at runtime.

Architecture Tactics:
  - Performance: Redis TTL of 5 minutes reduces DB reads.
  - Availability: Redis failures fall back to DB silently; if the embedding
    model is unavailable, ranking falls back to keyword-only relevance.
  - Modifiability: Skills-hash keeps personalised/generic caches independent.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.rss_item import NormalizedRssItem, RssAggregationResponse
from app.services.matching.semantic import item_similarities, query_vector
from app.services.rss.cache_service import cache_service
from app.services.redis_cache import redis_cache
from app.workers.rss_refresh_worker import trigger_manual_refresh

router = APIRouter(prefix="/feeds", tags=["feeds"])

# ── TTL constants ─────────────────────────────────────────────────────────────
_FEED_TTL = 300    # 5 minutes for feed slices
_ITEM_TTL = 1800   # 30 minutes for single-item hotspot cache


# ── Relevance Scoring (Strategy Pattern) ─────────────────────────────────────

def _normalise_token(s: str) -> str:
    return s.strip().lower()


def _relevance_score(item: NormalizedRssItem, skill_set: set[str]) -> int:
    """
    Compute relevance of an opportunity against the user's skill/interest set.

    Scoring weights (additive):
      +4  per skill found in tags         (most specific — curated metadata)
      +2  per skill found in title words  (strong signal — headline match)
      +1  per skill found in summary text (weak signal — body mention)

    The higher the score, the more relevant the item is to the user.
    Items with score == 0 are ranked last (after all matches).
    """
    if not skill_set:
        return 0

    score = 0

    # Tag match (strongest signal)
    tag_tokens = {_normalise_token(t) for t in item.tags}
    score += len(tag_tokens & skill_set) * 4

    # Title word match
    title_tokens = {_normalise_token(w) for w in item.title.split()}
    score += len(title_tokens & skill_set) * 2

    # Summary text match (partial — check if any skill appears as substring)
    summary_lower = item.summary.lower()
    for skill in skill_set:
        if len(skill) >= 3 and skill in summary_lower:  # avoid tiny noise tokens
            score += 1

    return score


def _recency_key(item: NormalizedRssItem) -> float:
    """Tie-breaker: newer first; undated items last (never compare None/str to datetime)."""
    return item.published_at.timestamp() if item.published_at else float("-inf")


def _build_skills_hash(skills: List[str]) -> str:
    """Stable 8-char hash of the sorted normalised skills list for cache keys."""
    normalised = sorted(_normalise_token(s) for s in skills if s.strip())
    return hashlib.md5(",".join(normalised).encode()).hexdigest()[:8]


# ── Feed Fetch Strategies (Strategy Pattern) ─────────────────────────────────

class FeedFetchStrategy(ABC):
    """Abstract strategy for fetching and ordering feed items."""

    @abstractmethod
    def execute(
        self,
        *,
        category: Optional[str],
        active_only: bool,
        resolved_limit: int,
        offset: int,
        skill_set: set[str],
    ) -> "RssAggregationResponse":
        ...


class RelevanceFetchStrategy(FeedFetchStrategy):
    """
    Relevance mode: fetch ALL items, score each one against the user's skill
    set, sort globally by score DESC, then apply pagination in Python.
    This guarantees the most relevant items surface regardless of DB page.
    """

    def execute(
        self,
        *,
        category: Optional[str],
        active_only: bool,
        resolved_limit: int,
        offset: int,
        skill_set: set[str],
    ) -> "RssAggregationResponse":
        all_result = cache_service.get_cached_feed(
            category=category,
            limit=2000,   # practical ceiling — DB rarely has more active items
            offset=0,
            active_only=active_only,
        )

        scored = [
            (item, _relevance_score(item, skill_set))
            for item in all_result.items
        ]

        scored.sort(key=lambda t: (t[1], _recency_key(t[0])), reverse=True)

        all_items_sorted = [item for item, _ in scored]
        total = len(all_items_sorted)
        page_items = all_items_sorted[offset: offset + resolved_limit]

        return RssAggregationResponse(
            items=page_items,
            sources=all_result.sources,
            total_items=total,
            fetched_at=all_result.fetched_at,
        )


class HybridRelevanceFetchStrategy(FeedFetchStrategy):
    """
    Semantic + keyword relevance (FR-4).

    Like RelevanceFetchStrategy it scores ALL active items before paginating,
    but the score blends:
      - cosine similarity between the item's embedding and the embedded
        skills list (computed by pgvector) — catches related wording such as
        "machine learning" ↔ "neural networks", and
      - the keyword score from `_relevance_score`, capped and scaled to 0..1 —
        keeps exact tag/title matches on top.
    Items not yet embedded get a semantic score of 0 until the embedding
    worker reaches them.
    """

    SEMANTIC_WEIGHT = 0.7
    KEYWORD_WEIGHT = 0.3
    KEYWORD_CAP = 10

    def __init__(self, query_vector: list[float]) -> None:
        self._query_vector = query_vector

    def execute(
        self,
        *,
        category: Optional[str],
        active_only: bool,
        resolved_limit: int,
        offset: int,
        skill_set: set[str],
    ) -> "RssAggregationResponse":
        all_result = cache_service.get_cached_feed(
            category=category,
            limit=2000,
            offset=0,
            active_only=active_only,
        )
        similarities = item_similarities(
            [i.id for i in all_result.items if i.id is not None], self._query_vector
        )

        def score(item: NormalizedRssItem) -> float:
            keyword = min(_relevance_score(item, skill_set), self.KEYWORD_CAP) / self.KEYWORD_CAP
            semantic = similarities.get(item.id, 0.0)
            return self.SEMANTIC_WEIGHT * semantic + self.KEYWORD_WEIGHT * keyword

        ranked = sorted(
            all_result.items, key=lambda i: (score(i), _recency_key(i)), reverse=True
        )
        return RssAggregationResponse(
            items=ranked[offset: offset + resolved_limit],
            sources=all_result.sources,
            total_items=len(ranked),
            fetched_at=all_result.fetched_at,
        )


class DefaultFetchStrategy(FeedFetchStrategy):
    """
    Default mode: standard paginated fetch from DB — no relevance scoring.
    """

    def execute(
        self,
        *,
        category: Optional[str],
        active_only: bool,
        resolved_limit: int,
        offset: int,
        skill_set: set[str],  # unused — kept for interface uniformity
    ) -> "RssAggregationResponse":
        return cache_service.get_cached_feed(
            category=category,
            limit=resolved_limit,
            offset=offset,
            active_only=active_only,
        )


# ── Main Feed Endpoint ────────────────────────────────────────────────────────

@router.get("/rss", response_model=RssAggregationResponse)
def list_rss_opportunities(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    category: Optional[str] = Query(None),
    active_only: bool = Query(True),
    skills: Optional[str] = Query(
        None,
        description=(
            "Comma-separated skills/interests from the user's resume profile. "
            "When provided, ALL matching items across the full dataset are scored "
            "and ranked BEFORE pagination is applied, so the most relevant items "
            "always surface regardless of which page they would normally appear on."
        ),
    ),
    limit_per_feed: Optional[int] = Query(None, ge=1, le=500),
) -> RssAggregationResponse:
    """
    Return opportunities from the DB, optionally re-ranked by skill relevance.

    CRITICAL DESIGN — Relevance mode vs. Default mode:

    Default mode (no skills):
        cache_service fetches `limit` rows with `offset` → standard pagination.
        Cache key: feed:{category}:{active}:{limit}:{offset}:none

    Relevance mode (skills provided):
        ALL items are fetched from DB (no limit), scored against the skill set,
        sorted by score DESC, then paginated in Python.
        This guarantees the globally most-relevant items are returned regardless
        of which DB page they reside on.
        Scoring is hybrid (semantic + keyword) when the embedding model is
        ready, keyword-only otherwise.
        Cache key: feed:{category}:{active}:{limit}:{offset}:{skills_hash}[-semantic]
        — separate key so personalised and generic caches never collide.
    """
    resolved_limit = limit_per_feed if limit_per_feed is not None else limit

    # Parse and normalise skills
    skill_list: List[str] = []
    skill_set: set[str] = set()
    if skills:
        skill_list = [s.strip() for s in skills.split(",") if s.strip()]
        skill_set = {_normalise_token(s) for s in skill_list}

    # Semantic vector for the skills (None → model not ready / disabled).
    vector = query_vector(skill_list) if skill_list else None

    skills_hash = _build_skills_hash(skill_list) if skill_list else "none"
    if vector is not None:
        skills_hash += "-semantic"  # keyword-only fallback results never share a key

    # ── Cache-Aside: check Redis first ───────────────────────────────────────
    cache_key = (
        f"feed:{category}:{str(active_only).lower()}:"
        f"{resolved_limit}:{offset}:{skills_hash}"
    )
    cached = redis_cache.get(cache_key)
    if cached is not None:
        response = RssAggregationResponse(**cached)
        response.from_cache = True
        return response

    # ── Cache MISS: select and execute the appropriate strategy ─────────────
    strategy: FeedFetchStrategy
    if vector is not None:
        strategy = HybridRelevanceFetchStrategy(vector)
    elif skill_set:
        strategy = RelevanceFetchStrategy()
    else:
        strategy = DefaultFetchStrategy()

    result = strategy.execute(
        category=category,
        active_only=active_only,
        resolved_limit=resolved_limit,
        offset=offset,
        skill_set=skill_set,
    )

    # ── Store in Redis ────────────────────────────────────────────────────────
    # Serialise BEFORE setting from_cache so the flag is never baked into Redis.
    redis_cache.set(cache_key, result.model_dump(mode="json"), ttl_seconds=_FEED_TTL)
    result.from_cache = False
    return result


# ── Supporting Endpoints ──────────────────────────────────────────────────────

@router.get("/rss/summary")
def rss_sources_summary() -> dict:
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
    return cache_service.get_cache_status()


@router.get("/items/{item_id}", response_model=NormalizedRssItem)
def get_item_by_id(item_id: int) -> NormalizedRssItem:
    """
    Fetch a single opportunity by its numeric id (the same id bookmarks use).
    Used by API clients such as the UniCompass MCP server.
    """
    item = cache_service.get_item_by_id(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Opportunity not found.")
    return item


@router.get("/rss/{item_id:path}", response_model=NormalizedRssItem)
def get_rss_item(item_id: str) -> NormalizedRssItem:
    """
    Fetch a single opportunity by GUID or URL.
    Cache-Aside: Redis key = opportunity:{item_id}, TTL 30 min.
    """
    cache_key = f"opportunity:{item_id}"
    cached = redis_cache.get(cache_key)
    if cached is not None:
        return NormalizedRssItem(**cached)

    item = cache_service.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Opportunity not found.")

    redis_cache.set(cache_key, item.model_dump(mode="json"), ttl_seconds=_ITEM_TTL)
    return item


@router.post("/rss/refresh")
async def rss_manual_refresh(
    category: Optional[str] = Query(None),
) -> dict:
    """Manually trigger background refresh on demand."""
    return await trigger_manual_refresh(category=category)
