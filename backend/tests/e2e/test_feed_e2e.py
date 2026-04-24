"""
E2E Tests — Feed Endpoints
============================
Tests the RSS feed API endpoints:
  GET /api/feeds/rss — paginated feed listing
  GET /api/feeds/rss/{item_id} — single item lookup
  GET /api/feeds/rss/summary — source summary
  GET /api/feeds/rss/cache-status — cache observability

These tests mock the cache_service to avoid needing real PostgreSQL
and feed sources, while still exercising the full HTTP → router → response
pipeline.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.schemas.rss_item import NormalizedRssItem, FeedSourceStatus, RssAggregationResponse


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_feed_response(count: int = 5, category: str = "job") -> RssAggregationResponse:
    """Build a fake feed response for mocking cache_service."""
    items = [
        NormalizedRssItem(
            id=i,
            title=f"Opportunity {i}",
            url=f"https://example.com/opp/{i}",
            summary=f"Summary for opportunity {i} with Python skills",
            published_at=datetime.now(timezone.utc),
            category=category,
            source_name="TestSource",
            feed_url="https://example.com/feed.xml",
            tags=["python", "react"],
            guid=f"guid-feed-{i}",
        )
        for i in range(count)
    ]
    return RssAggregationResponse(
        items=items,
        sources=[
            FeedSourceStatus(
                feed_url="https://example.com/feed.xml",
                category=category,
                source_name="TestSource",
                ok=True,
                http_status=200,
                entries_fetched=count,
                items_normalized=count,
            )
        ],
        total_items=count,
        fetched_at=datetime.now(timezone.utc),
    )


# ── Tests ────────────────────────────────────────────────────────────────────

class TestListRssOpportunities:
    """GET /api/feeds/rss — paginated feed listing."""

    @patch("app.routers.feeds.cache_service")
    def test_returns_items_and_metadata(
        self, mock_cache_svc: MagicMock, client: TestClient
    ):
        feed_resp = _make_feed_response(5)
        mock_cache_svc.get_cached_feed.return_value = feed_resp

        resp = client.get("/api/feeds/rss?limit=5&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total_items" in data
        assert "fetched_at" in data
        assert len(data["items"]) == 5

    @patch("app.routers.feeds.cache_service")
    def test_pagination_offset(
        self, mock_cache_svc: MagicMock, client: TestClient
    ):
        feed_resp = _make_feed_response(10)
        mock_cache_svc.get_cached_feed.return_value = feed_resp

        # Request with offset=3, limit=3
        resp = client.get("/api/feeds/rss?limit=3&offset=3")
        assert resp.status_code == 200

    @patch("app.routers.feeds.cache_service")
    def test_category_filter(
        self, mock_cache_svc: MagicMock, client: TestClient
    ):
        feed_resp = _make_feed_response(3, category="internship")
        mock_cache_svc.get_cached_feed.return_value = feed_resp

        resp = client.get("/api/feeds/rss?category=internship")
        assert resp.status_code == 200
        data = resp.json()
        assert all(item["category"] == "internship" for item in data["items"])

    @patch("app.routers.feeds.cache_service")
    def test_skills_relevance_scoring(
        self, mock_cache_svc: MagicMock, client: TestClient
    ):
        """When skills are provided, items should be re-ranked by relevance."""
        feed_resp = _make_feed_response(5)
        mock_cache_svc.get_cached_feed.return_value = feed_resp

        resp = client.get("/api/feeds/rss?skills=python,react")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) > 0


class TestGetSingleRssItem:
    """GET /api/feeds/rss/{item_id} — single item lookup."""

    @patch("app.routers.feeds.cache_service")
    def test_get_existing_item(
        self, mock_cache_svc: MagicMock, client: TestClient
    ):
        feed_resp = _make_feed_response(3)
        mock_cache_svc.get_cached_feed.return_value = feed_resp

        resp = client.get("/api/feeds/rss/guid-feed-0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["guid"] == "guid-feed-0"
        assert data["title"] == "Opportunity 0"

    @patch("app.routers.feeds.cache_service")
    def test_get_nonexistent_item_returns_404(
        self, mock_cache_svc: MagicMock, client: TestClient
    ):
        feed_resp = _make_feed_response(0)
        mock_cache_svc.get_cached_feed.return_value = feed_resp

        resp = client.get("/api/feeds/rss/nonexistent-guid")
        assert resp.status_code == 404


class TestRssSummary:
    """GET /api/feeds/rss/summary — feed source summary."""

    def test_summary_returns_category_counts(self, client: TestClient):
        resp = client.get("/api/feeds/rss/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_sources" in data
        assert "by_category" in data
        assert "generated_at" in data
        assert isinstance(data["by_category"], dict)


class TestRssCacheStatus:
    """GET /api/feeds/rss/cache-status — cache observability."""

    @patch("app.routers.feeds.cache_service")
    def test_cache_status_endpoint(
        self, mock_cache_svc: MagicMock, client: TestClient
    ):
        mock_cache_svc.get_cache_status.return_value = {
            "categories": [],
            "total_items": 0,
            "checked_at": datetime.now(timezone.utc).isoformat() + "Z",
        }

        resp = client.get("/api/feeds/rss/cache-status")
        assert resp.status_code == 200
        data = resp.json()
        assert "categories" in data
        assert "total_items" in data
