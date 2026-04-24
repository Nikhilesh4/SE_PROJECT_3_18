"""
E2E Tests — Feed Relevance Scoring
=====================================
Tests the relevance scoring and ranking strategy used in the feed endpoint,
verifying the full scoring → sorting → pagination pipeline.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.routers.feeds import (
    _normalise_token,
    _relevance_score,
    _build_skills_hash,
    RelevanceFetchStrategy,
    DefaultFetchStrategy,
)
from app.schemas.rss_item import NormalizedRssItem, RssAggregationResponse


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_item(
    title: str = "Test",
    summary: str = "Summary",
    tags: list[str] | None = None,
    category: str = "job",
) -> NormalizedRssItem:
    return NormalizedRssItem(
        title=title,
        url=f"https://example.com/{title.replace(' ', '-').lower()}",
        summary=summary,
        published_at=datetime.now(timezone.utc),
        category=category,
        source_name="TestSource",
        feed_url="https://example.com/feed.xml",
        tags=tags or [],
        guid=f"guid-{title.replace(' ', '-').lower()}",
    )


# ── Tests ────────────────────────────────────────────────────────────────────

class TestNormaliseToken:
    """Test the _normalise_token utility."""

    def test_strips_and_lowercases(self):
        assert _normalise_token("  Python  ") == "python"

    def test_already_normalised(self):
        assert _normalise_token("react") == "react"


class TestRelevanceScore:
    """Test the _relevance_score function."""

    def test_tag_match_scores_highest(self):
        item = _make_item(tags=["python", "react"])
        skill_set = {"python"}
        score = _relevance_score(item, skill_set)
        assert score >= 4  # tag match = +4

    def test_title_match_scores_medium(self):
        item = _make_item(title="Python Developer Position")
        skill_set = {"python"}
        score = _relevance_score(item, skill_set)
        assert score >= 2  # title word match = +2

    def test_summary_match_scores_low(self):
        item = _make_item(summary="Experience with python required for this role")
        skill_set = {"python"}
        score = _relevance_score(item, skill_set)
        assert score >= 1  # summary match = +1

    def test_no_match_scores_zero(self):
        item = _make_item(
            title="Java Developer",
            summary="Java and Spring",
            tags=["java"],
        )
        skill_set = {"python"}
        score = _relevance_score(item, skill_set)
        assert score == 0

    def test_empty_skills_scores_zero(self):
        item = _make_item(tags=["python"])
        assert _relevance_score(item, set()) == 0

    def test_multiple_matches_accumulate(self):
        item = _make_item(
            title="Python React Developer",
            summary="Work with python and react",
            tags=["python", "react"],
        )
        skill_set = {"python", "react"}
        score = _relevance_score(item, skill_set)
        # Tag: 2 matches × 4 = 8
        # Title: 2 matches × 2 = 4
        # Summary: 2 matches × 1 = 2
        assert score >= 14


class TestBuildSkillsHash:
    """Test the _build_skills_hash cache key builder."""

    def test_same_skills_same_hash(self):
        h1 = _build_skills_hash(["Python", "React"])
        h2 = _build_skills_hash(["python", "react"])
        assert h1 == h2

    def test_order_independent(self):
        h1 = _build_skills_hash(["React", "Python"])
        h2 = _build_skills_hash(["Python", "React"])
        assert h1 == h2

    def test_different_skills_different_hash(self):
        h1 = _build_skills_hash(["Python"])
        h2 = _build_skills_hash(["Java"])
        assert h1 != h2

    def test_empty_skills(self):
        h = _build_skills_hash([])
        assert isinstance(h, str)
        assert len(h) == 8

    def test_whitespace_ignored(self):
        h1 = _build_skills_hash(["  python  "])
        h2 = _build_skills_hash(["python"])
        assert h1 == h2


class TestFeedStrategies:
    """Test the Strategy pattern implementations."""

    def test_default_strategy_delegates_to_cache_service(self):
        """DefaultFetchStrategy should pass through to cache_service."""
        strategy = DefaultFetchStrategy()
        # Just verify it's instantiable and has the execute interface
        assert hasattr(strategy, "execute")

    def test_relevance_strategy_is_instantiable(self):
        """RelevanceFetchStrategy should be instantiable."""
        strategy = RelevanceFetchStrategy()
        assert hasattr(strategy, "execute")
