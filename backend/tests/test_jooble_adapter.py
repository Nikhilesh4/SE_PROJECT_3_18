"""Unit tests for JoobleAdapter."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services.adapters.jooble_adapter import JoobleAdapter


# ── Fixtures ─────────────────────────────────────────────────────────────

SAMPLE_JOOBLE_RESPONSE = {
    "totalCount": 2,
    "jobs": [
        {
            "title": "Python Developer",
            "location": "Remote",
            "snippet": "We are looking for a Python developer with 2+ years of experience.",
            "salary": "$80,000 - $120,000",
            "source": "CompanyJobs",
            "type": "Full-time",
            "link": "https://example.com/jobs/python-dev-1",
            "company": "TechCorp",
            "updated": "2026-04-15T00:00:00.0000000",
            "id": "12345",
        },
        {
            "title": "Data Science Intern",
            "location": "New York",
            "snippet": "Join our data science team as an intern.",
            "salary": "",
            "source": "InternBoard",
            "type": "Internship",
            "link": "https://example.com/jobs/ds-intern-2",
            "company": "DataInc",
            "updated": "2026-04-14T10:30:00.0000000",
            "id": "67890",
        },
    ],
}

EMPTY_JOOBLE_RESPONSE = {"totalCount": 0, "jobs": []}


# ── Tests ────────────────────────────────────────────────────────────────


class TestJoobleAdapterNormalization:
    """Test that Jooble API responses are correctly normalized."""

    def setup_method(self):
        self.adapter = JoobleAdapter(api_key="test-api-key")

    @patch("app.services.adapters.jooble_adapter.httpx.Client")
    def test_fetch_returns_normalized_items(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_JOOBLE_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        results = self.adapter.fetch_opportunities(keywords="python developer")

        assert len(results) == 2
        assert results[0].title == "Python Developer"
        assert results[0].source_name == "Jooble"
        assert results[0].feed_url == "jooble-api"
        assert results[0].url == "https://example.com/jobs/python-dev-1"
        assert results[0].guid == "jooble:12345"
        assert results[0].category == "job"

    @patch("app.services.adapters.jooble_adapter.httpx.Client")
    def test_intern_category_detection(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_JOOBLE_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        results = self.adapter.fetch_opportunities(keywords="data science internship")

        # The second job ("Data Science Intern") should be categorized as internship
        intern_items = [r for r in results if r.category == "internship"]
        assert len(intern_items) >= 1

    @patch("app.services.adapters.jooble_adapter.httpx.Client")
    def test_empty_response(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = EMPTY_JOOBLE_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        results = self.adapter.fetch_opportunities(keywords="nonexistent job xyz")
        assert results == []

    @patch("app.services.adapters.jooble_adapter.httpx.Client")
    def test_network_error_returns_empty(self, mock_client_cls):
        import httpx as _httpx

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.side_effect = _httpx.RequestError("connection timeout")
        mock_client_cls.return_value = mock_client

        results = self.adapter.fetch_opportunities(keywords="python")
        assert results == []

    @patch("app.services.adapters.jooble_adapter.settings")
    def test_no_api_key_returns_empty(self, mock_settings):
        mock_settings.JOOBLE_API_KEY = ""
        adapter = JoobleAdapter(api_key="")
        results = adapter.fetch_opportunities(keywords="python")
        assert results == []


class TestJoobleAdapterHelpers:
    """Test internal helper methods."""

    def test_parse_date_valid(self):
        dt = JoobleAdapter._parse_date("2026-04-15T00:00:00.0000000")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 4
        assert dt.day == 15
        assert dt.tzinfo == timezone.utc

    def test_parse_date_empty(self):
        assert JoobleAdapter._parse_date("") is None

    def test_parse_date_invalid(self):
        assert JoobleAdapter._parse_date("not-a-date") is None

    def test_infer_category_job(self):
        assert JoobleAdapter._infer_category("Software Engineer", "", "python") == "job"

    def test_infer_category_internship(self):
        assert JoobleAdapter._infer_category("Data Science Intern", "", "") == "internship"

    def test_infer_category_research(self):
        assert JoobleAdapter._infer_category("Research Assistant", "", "") == "research"

    def test_infer_category_freelance(self):
        assert JoobleAdapter._infer_category("Freelance Developer", "", "") == "freelance"

    def test_build_summary(self):
        job = {
            "company": "TechCorp",
            "location": "Remote",
            "salary": "$100k",
            "type": "Full-time",
            "source": "CompanyJobs",
        }
        summary = JoobleAdapter._build_summary(job, "Great opportunity")
        assert "Company: TechCorp" in summary
        assert "Location: Remote" in summary
        assert "Great opportunity" in summary

    def test_normalize_job_skips_empty_title(self):
        job = {"title": "", "link": "https://example.com"}
        assert JoobleAdapter._normalize_job(job, "python") is None

    def test_normalize_job_skips_empty_link(self):
        job = {"title": "Some Job", "link": ""}
        assert JoobleAdapter._normalize_job(job, "python") is None
