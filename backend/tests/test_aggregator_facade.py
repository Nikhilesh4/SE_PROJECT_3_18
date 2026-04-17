"""Unit tests for AggregatorFacade."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.schemas.rss_item import NormalizedRssItem, RssAggregationResponse
from app.services.adapters.aggregator_facade import AggregatorFacade
from app.services.adapters.base_adapter import OpportunityAdapter


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_item(url: str, title: str = "Test", source: str = "TestSource") -> NormalizedRssItem:
    return NormalizedRssItem(
        title=title,
        url=url,
        summary="summary",
        published_at=datetime.now(timezone.utc),
        category="job",
        source_name=source,
        feed_url="https://example.com/feed",
        tags=[],
        guid=f"guid-{url}",
    )


class _StubAdapter(OpportunityAdapter):
    """Minimal adapter for testing — returns a fixed list of items."""

    def __init__(self, items: list[NormalizedRssItem]) -> None:
        self._items = items

    def fetch_opportunities(self, **kwargs) -> list[NormalizedRssItem]:
        return self._items


class _FailingAdapter(OpportunityAdapter):
    """Adapter that always raises."""

    def fetch_opportunities(self, **kwargs) -> list[NormalizedRssItem]:
        raise RuntimeError("intentional failure")


# ── Tests ────────────────────────────────────────────────────────────────


class TestAggregatorFacadeNoRSS:
    """Test the facade with include_rss=False so we don't hit real feeds."""

    def test_merges_items_from_multiple_adapters(self):
        adapter_a = _StubAdapter([_make_item("https://a.com/1"), _make_item("https://a.com/2")])
        adapter_b = _StubAdapter([_make_item("https://b.com/1")])

        facade = AggregatorFacade(adapters=[adapter_a, adapter_b], include_rss=False)
        results = facade.fetch_all_opportunities()

        assert len(results) == 3
        urls = {item.url for item in results}
        assert urls == {"https://a.com/1", "https://a.com/2", "https://b.com/1"}

    def test_deduplicates_by_url(self):
        """Same URL from two adapters should appear only once."""
        shared_url = "https://shared.com/job-1"
        adapter_a = _StubAdapter([_make_item(shared_url, source="SourceA")])
        adapter_b = _StubAdapter([_make_item(shared_url, source="SourceB")])

        facade = AggregatorFacade(adapters=[adapter_a, adapter_b], include_rss=False)
        results = facade.fetch_all_opportunities()

        assert len(results) == 1
        # The first adapter's item should win
        assert results[0].source_name == "SourceA"

    def test_empty_adapters_return_empty(self):
        adapter = _StubAdapter([])
        facade = AggregatorFacade(adapters=[adapter], include_rss=False)
        results = facade.fetch_all_opportunities()
        assert results == []

    def test_failing_adapter_does_not_break_others(self):
        good_adapter = _StubAdapter([_make_item("https://good.com/1")])
        bad_adapter = _FailingAdapter()

        facade = AggregatorFacade(
            adapters=[bad_adapter, good_adapter], include_rss=False
        )
        results = facade.fetch_all_opportunities()

        # Should still get the good adapter's results
        assert len(results) == 1
        assert results[0].url == "https://good.com/1"

    def test_no_adapters_returns_empty(self):
        facade = AggregatorFacade(adapters=[], include_rss=False)
        results = facade.fetch_all_opportunities()
        assert results == []


class TestAggregatorFacadeWithRSS:
    """Test that the RSS aggregator integration works."""

    @patch("app.services.adapters.aggregator_facade.aggregate_all_feeds")
    def test_rss_items_are_included(self, mock_agg):
        rss_items = [_make_item("https://rss.com/1"), _make_item("https://rss.com/2")]
        mock_agg.return_value = RssAggregationResponse(
            items=rss_items,
            sources=[],
            total_items=2,
            fetched_at=datetime.now(timezone.utc),
        )

        facade = AggregatorFacade(adapters=[], include_rss=True)
        results = facade.fetch_all_opportunities()

        assert len(results) == 2
        mock_agg.assert_called_once_with(limit_per_feed=50)

    @patch("app.services.adapters.aggregator_facade.aggregate_all_feeds")
    def test_rss_dedup_with_adapters(self, mock_agg):
        shared_url = "https://overlap.com/1"
        mock_agg.return_value = RssAggregationResponse(
            items=[_make_item(shared_url, source="RSS")],
            sources=[],
            total_items=1,
            fetched_at=datetime.now(timezone.utc),
        )
        adapter = _StubAdapter([_make_item(shared_url, source="API")])

        facade = AggregatorFacade(adapters=[adapter], include_rss=True)
        results = facade.fetch_all_opportunities()

        # Shared URL should appear only once (RSS comes first)
        assert len(results) == 1
        assert results[0].source_name == "RSS"

    @patch("app.services.adapters.aggregator_facade.aggregate_all_feeds")
    def test_rss_failure_allows_adapters_to_proceed(self, mock_agg):
        mock_agg.side_effect = RuntimeError("RSS failed")
        adapter = _StubAdapter([_make_item("https://api.com/1")])

        facade = AggregatorFacade(adapters=[adapter], include_rss=True)
        results = facade.fetch_all_opportunities()

        assert len(results) == 1
        assert results[0].url == "https://api.com/1"
