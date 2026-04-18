"""Fetch all configured feeds and normalize entries through a shared interface."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

import feedparser
import httpx

from app.schemas.rss_item import FeedSourceStatus, NormalizedRssItem, RssAggregationResponse
from app.services.rss.adzuna_adapter import AdzunaAdapter
from app.services.rss.feed_sources import FEED_SOURCES, FeedSource
from app.services.rss.filter import is_opportunity_post
from app.services.rss.normalize import RssEntryNormalizer, default_normalize_entry

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
}


def fetch_parse_feed(
    url: str,
    *,
    client: httpx.Client | None = None,
    timeout: float = 25.0,
) -> tuple[int | None, feedparser.FeedParserDict, str | None]:
    """
    HTTP GET + feedparser.parse.
    Returns (status_code, parsed_feed, error_message).
    """
    own_client = client is None
    if client is None:
        client = httpx.Client(timeout=timeout, headers=DEFAULT_HEADERS, follow_redirects=True)
    try:
        r = client.get(url)
        status = r.status_code
        if status != 200:
            return status, feedparser.FeedParserDict(), f"HTTP {status}"
        parsed = feedparser.parse(r.content)
        return status, parsed, None
    except httpx.RequestError as e:
        return None, feedparser.FeedParserDict(), str(e)
    finally:
        if own_client:
            client.close()


def ingest_feed_source(
    source: FeedSource,
    *,
    limit: int | None = None,
    normalizer: RssEntryNormalizer = default_normalize_entry,
    client: httpx.Client | None = None,
) -> tuple[list[NormalizedRssItem], FeedSourceStatus]:
    status = FeedSourceStatus(
        feed_url=source.url,
        category=source.category,
        source_name=source.source_name,
        ok=False,
        http_status=None,
        error=None,
        entries_fetched=0,
        items_normalized=0,
    )
    code, parsed, err = fetch_parse_feed(source.url, client=client)
    status.http_status = code
    if err:
        status.error = err
        return [], status

    entries = list(parsed.entries)
    if limit is not None:
        entries = entries[:limit]
    status.entries_fetched = len(entries)

    items: list[NormalizedRssItem] = []
    for entry in entries:
        # feedparser entries are dict-like
        e: Mapping[str, Any] = entry
        norm = normalizer(
            e,
            category=source.category,
            source_name=source.source_name,
            feed_url=source.url,
        )
        if norm is not None:
            items.append(norm)

    status.items_normalized = len(items)
    status.ok = True
    return items, status


def aggregate_all_feeds(
    *,
    limit_per_feed: int | None = 10,
    category_filter: str | None = None,
    normalizer: RssEntryNormalizer = default_normalize_entry,
) -> RssAggregationResponse:
    """
    Walk every FeedSource, fetch, normalize via `normalizer` (Protocol).
    Also calls AdzunaAdapter to supplement with live job/internship listings.

    `limit_per_feed`: max entries taken from each feed after parse (None = all).
    `category_filter`: if set, only sources with this category string.
    """
    sources_to_run = FEED_SOURCES
    if category_filter:
        sources_to_run = tuple(s for s in FEED_SOURCES if s.category == category_filter)

    all_items: list[NormalizedRssItem] = []
    statuses: list[FeedSourceStatus] = []
    fetched_at = datetime.now(timezone.utc)

    with httpx.Client(timeout=25.0, headers=DEFAULT_HEADERS, follow_redirects=True) as client:
        for src in sources_to_run:
            items, st = ingest_feed_source(
                src,
                limit=limit_per_feed,
                normalizer=normalizer,
                client=client,
            )
            all_items.extend(items)
            statuses.append(st)

    # ── Adzuna API adapter ────────────────────────────────────────────────
    # Only run if no category filter OR the filter applies to job/internship.
    _adzuna_categories = {"internship", "job"}
    if category_filter is None or category_filter in _adzuna_categories:
        adzuna = AdzunaAdapter()
        adzuna_ok = False
        adzuna_count = 0
        adzuna_error: str | None = None
        try:
            if category_filter:
                adzuna_items = adzuna.fetch_for_category(category_filter)
            else:
                adzuna_items = adzuna.fetch_all()
            all_items.extend(adzuna_items)
            adzuna_count = len(adzuna_items)
            adzuna_ok = True
        except Exception as exc:  # noqa: BLE001
            adzuna_error = str(exc)

        statuses.append(
            FeedSourceStatus(
                feed_url="https://api.adzuna.com/v1/api/jobs",
                category=category_filter or "job",
                source_name="Adzuna API",
                ok=adzuna_ok,
                http_status=200 if adzuna_ok else None,
                error=adzuna_error,
                entries_fetched=adzuna_count,
                items_normalized=adzuna_count,
            )
        )

    # ── Jooble API adapter (for job/internship categories) ──────────
    if category_filter is None or category_filter in ("job", "internship"):
        try:
            jooble_items = fetch_jooble_opportunities()
            all_items.extend(jooble_items)
            statuses.append(
                FeedSourceStatus(
                    feed_url="jooble-api",
                    category="job",
                    source_name="Jooble",
                    ok=True,
                    http_status=200,
                    error=None,
                    entries_fetched=len(jooble_items),
                    items_normalized=len(jooble_items),
                )
            )
        except Exception as e:
            statuses.append(
                FeedSourceStatus(
                    feed_url="jooble-api",
                    category="job",
                    source_name="Jooble",
                    ok=False,
                    http_status=None,
                    error=str(e),
                    entries_fetched=0,
                    items_normalized=0,
                )
            )

    # ── Apply content filter to reject blog/news articles ──────────────
    all_items = [
        item for item in all_items
        if is_opportunity_post(item.title, item.summary, item.category)
    ]

    return RssAggregationResponse(
        items=all_items,
        sources=statuses,
        total_items=len(all_items),
        fetched_at=fetched_at,
    )



def fetch_jooble_opportunities() -> list[NormalizedRssItem]:
    """Convenience wrapper: instantiate JoobleAdapter and run default queries."""
    from app.services.adapters.jooble_adapter import JoobleAdapter

    adapter = JoobleAdapter()
    return adapter.fetch_all_default_queries()
