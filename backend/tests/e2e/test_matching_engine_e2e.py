"""
E2E Tests — Matching Engine
=============================
Tests the semantic matching engine that scores new opportunities against
user profiles and generates notifications.
"""

from __future__ import annotations

import pytest

from app.services.matching_engine import _score_match, _tokenize, _profile_terms
from app.models.profile import Profile


class TestTokenizer:
    """Test the _tokenize helper."""

    def test_basic_tokenization(self):
        tokens = _tokenize("Python Developer at Google")
        assert "python" in tokens
        assert "developer" in tokens
        assert "google" in tokens

    def test_special_characters_preserved(self):
        tokens = _tokenize("C++ and C# developer")
        assert "c++" in tokens
        assert "c#" in tokens

    def test_empty_string(self):
        assert _tokenize("") == set()

    def test_none_input(self):
        assert _tokenize(None) == set()


class TestScoreMatch:
    """Test the _score_match relevance function."""

    def test_perfect_tag_match(self):
        profile_terms = {"python", "react", "docker"}
        item = {
            "title": "Generic Title",
            "summary": "Some summary",
            "tags": ["Python", "React", "Docker"],
        }
        score = _score_match(profile_terms, item)
        assert score > 0.0
        assert score <= 1.0

    def test_title_match_scores_medium(self):
        profile_terms = {"python", "fastapi"}
        item = {
            "title": "Python FastAPI Developer Needed",
            "summary": "No relevant content here.",
            "tags": [],
        }
        score = _score_match(profile_terms, item)
        assert score > 0.0

    def test_summary_match_scores_low(self):
        profile_terms = {"kubernetes"}
        item = {
            "title": "Generic Dev Job",
            "summary": "Experience with kubernetes preferred",
            "tags": [],
        }
        score = _score_match(profile_terms, item)
        assert score > 0.0

    def test_no_match_scores_zero(self):
        profile_terms = {"haskell", "erlang"}
        item = {
            "title": "Python Developer",
            "summary": "Python and React experience required",
            "tags": ["python", "react"],
        }
        score = _score_match(profile_terms, item)
        assert score == 0.0

    def test_empty_profile_scores_zero(self):
        score = _score_match(set(), {"title": "X", "summary": "Y", "tags": ["Z"]})
        assert score == 0.0

    def test_tag_match_weighs_more_than_title(self):
        """Tags should provide stronger signal than title."""
        profile_terms = {"python"}
        tag_item = {
            "title": "Generic Job",
            "summary": "Summary",
            "tags": ["python"],
        }
        title_item = {
            "title": "Python Developer",
            "summary": "Summary",
            "tags": [],
        }
        tag_score = _score_match(profile_terms, tag_item)
        title_score = _score_match(profile_terms, title_item)
        assert tag_score > title_score


class TestProfileTerms:
    """Test _profile_terms extraction from Profile ORM objects."""

    def test_extracts_skills_and_interests(self):
        profile = Profile(
            user_id=1,
            parsed_skills=["Python", "React", "Docker"],
            parsed_interests=["Machine Learning", "AI"],
        )
        terms = _profile_terms(profile)
        assert "python" in terms
        assert "react" in terms
        assert "machine learning" in terms
        # Short terms (< 2 chars) should be filtered
        assert all(len(t) >= 2 for t in terms)

    def test_handles_none_fields(self):
        profile = Profile(
            user_id=1,
            parsed_skills=None,
            parsed_interests=None,
        )
        terms = _profile_terms(profile)
        assert terms == set()

    def test_deduplicates_and_normalizes(self):
        profile = Profile(
            user_id=1,
            parsed_skills=["Python", "python", "PYTHON"],
            parsed_interests=[],
        )
        terms = _profile_terms(profile)
        assert terms == {"python"}
