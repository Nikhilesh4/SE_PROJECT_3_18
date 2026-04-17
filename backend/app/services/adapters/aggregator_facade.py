"""
AggregatorFacade — Facade pattern for the RSS Ingestion Engine.

Provides a single ``fetch_all_opportunities()`` method that calls every
registered adapter (RSS feeds, Adzuna, Jooble) and merges the results into
one unified, deduplicated list of ``NormalizedRssItem`` objects.

Usage::

    facade = AggregatorFacade()
    all_items = facade.fetch_all_opportunities()
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.schemas.rss_item import NormalizedRssItem
from app.services.adapters.base_adapter import OpportunityAdapter
from app.services.adapters.jooble_adapter import JoobleAdapter
from app.services.rss.adzuna_adapter import AdzunaAdapter
from app.services.rss.aggregator import aggregate_all_feeds

logger = logging.getLogger("adapters.aggregator_facade")


class AggregatorFacade:
    """
    Facade that aggregates opportunities from every external source.

    The constructor accepts an optional list of ``OpportunityAdapter``
    instances.  When none are supplied it auto-registers the default
    adapters (AdzunaAdapter, JoobleAdapter) and wraps the RSS feed
    aggregator as an internal source.

    Design notes
    ------------
    * **Facade pattern** — downstream code (the ingestion worker, API
      endpoints) only needs to call ``fetch_all_opportunities()`` and
      never worries about individual adapters.
    * **Deduplication** — results are deduplicated by source URL so the
      same opportunity surfaced by multiple sources appears only once.
    * **Fault isolation** — if one adapter raises, the others still
      contribute their results.
    """

    def __init__(
        self,
        adapters: list[OpportunityAdapter] | None = None,
        *,
        include_rss: bool = True,
    ) -> None:
        if adapters is not None:
            self._adapters = list(adapters)
        else:
            self._adapters: list[OpportunityAdapter] = [
                AdzunaAdapter(),
                JoobleAdapter(),
            ]
        self._include_rss = include_rss

    # ── Public interface ────────────────────────────────────────────

    def fetch_all_opportunities(self) -> list[NormalizedRssItem]:
        """
        Call every adapter, merge results, and deduplicate by source URL.

        Returns
        -------
        list[NormalizedRssItem]
            A flat, deduplicated list of opportunities from all sources.
        """
        merged: list[NormalizedRssItem] = []
        seen_urls: set[str] = set()

        # ── 1. RSS feeds (via the existing aggregator) ──────────────
        if self._include_rss:
            self._ingest_rss_feeds(merged, seen_urls)

        # ── 2. Each registered OpportunityAdapter ───────────────────
        for adapter in self._adapters:
            self._ingest_adapter(adapter, merged, seen_urls)

        logger.info(
            "AggregatorFacade: total unique opportunities = %d", len(merged)
        )
        return merged

    # ── Private helpers ─────────────────────────────────────────────

    def _ingest_rss_feeds(
        self,
        merged: list[NormalizedRssItem],
        seen_urls: set[str],
    ) -> None:
        """Fetch RSS feeds via the existing aggregator and append new items."""
        try:
            rss_response = aggregate_all_feeds(limit_per_feed=50)
            self._dedup_extend(merged, seen_urls, rss_response.items)
            logger.info(
                "AggregatorFacade: RSS feeds → %d unique items so far",
                len(merged),
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("AggregatorFacade: RSS aggregation failed: %s", exc)

    def _ingest_adapter(
        self,
        adapter: OpportunityAdapter,
        merged: list[NormalizedRssItem],
        seen_urls: set[str],
    ) -> None:
        """Fetch from a single adapter and append new items."""
        adapter_name = type(adapter).__name__
        try:
            items = self._fetch_from_adapter(adapter)
            before = len(merged)
            self._dedup_extend(merged, seen_urls, items)
            added = len(merged) - before
            logger.info(
                "AggregatorFacade: %s → %d items (%d new after dedup)",
                adapter_name,
                len(items),
                added,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "AggregatorFacade: %s failed: %s", adapter_name, exc
            )

    @staticmethod
    def _dedup_extend(
        merged: list[NormalizedRssItem],
        seen_urls: set[str],
        items: list[NormalizedRssItem],
    ) -> None:
        """Append items to *merged* that haven't been seen (by URL) yet."""
        for item in items:
            if item.url not in seen_urls:
                seen_urls.add(item.url)
                merged.append(item)

    @staticmethod
    def _fetch_from_adapter(adapter: OpportunityAdapter) -> list[NormalizedRssItem]:
        """
        Dispatch to the right fetch method depending on adapter type.

        * ``JoobleAdapter`` exposes ``fetch_all_default_queries()`` which
          runs multiple keyword searches and deduplicates internally.
        * ``AdzunaAdapter`` exposes ``fetch_all()`` for the same purpose.
        * Any generic ``OpportunityAdapter`` uses ``fetch_opportunities()``.
        """
        if isinstance(adapter, JoobleAdapter):
            return adapter.fetch_all_default_queries()
        if isinstance(adapter, AdzunaAdapter):
            return adapter.fetch_all()
        # Fallback for any custom adapter implementing OpportunityAdapter
        return adapter.fetch_opportunities()
