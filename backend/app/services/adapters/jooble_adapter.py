"""
JoobleAdapter — fetches job listings from the Jooble REST API.

Jooble docs: https://jooble.org/api/about

Request:  POST https://jooble.org/api/{api_key}
          Body: { "keywords": "...", "location": "...", "page": 1 }

Response: { "totalCount": N, "jobs": [ { "title", "location", "snippet",
            "salary", "source", "type", "link", "company", "updated",
            "id" }, ... ] }
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.schemas.rss_item import NormalizedRssItem
from app.services.adapters.base_adapter import OpportunityAdapter
from app.services.redis_cache import redis_cache

logger = logging.getLogger("adapters.jooble")

_JOOBLE_API_URL = "https://jooble.org/api/{api_key}"
_TIMEOUT_SECONDS = 20.0

# Jooble search queries used during periodic ingestion.
# Each tuple is (keywords, location).
DEFAULT_SEARCH_QUERIES: list[tuple[str, str]] = [
    ("software engineer intern", ""),
    ("python developer", ""),
    ("data science internship", ""),
    ("frontend developer remote", ""),
    ("machine learning engineer", ""),
    ("backend developer", ""),
    ("full stack developer", ""),
    ("devops engineer", ""),
]


class JoobleAdapter(OpportunityAdapter):
    """Adapter that normalizes Jooble API responses into NormalizedRssItem."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.JOOBLE_API_KEY
        if not self._api_key:
            logger.warning("JOOBLE_API_KEY is empty — adapter will return no results")

    # ── Public interface ────────────────────────────────────────────
    def fetch_opportunities(
        self,
        *,
        keywords: str = "",
        location: str = "",
        page: int = 1,
        limit: int = 20,
    ) -> list[NormalizedRssItem]:
        """
        Call the Jooble API and return normalized opportunity items.

        Parameters
        ----------
        keywords : str
            Search terms (e.g. "python developer").
        location : str
            Location filter (e.g. "remote", "New York").
        page : int
            1-indexed page number.
        limit : int
            Not directly supported by Jooble (they return ~20 per page),
            but we trim to this many results.
        """
        if not self._api_key:
            return []

        url = _JOOBLE_API_URL.format(api_key=self._api_key)
        payload = {
            "keywords": keywords,
            "location": location,
            "page": str(page),
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        }

        # ── Source Cache-Aside (Ingestion Side) ─────────────────────────
        # Key: source:jooble:{keywords}:{location}:{page}:latest
        # TTL: 30 minutes — prevents redundant external API calls if the
        # ingestion worker retries after a crash and helps stay within rate limits.
        _src_key = f"source:jooble:{keywords}:{location}:{page}:latest"
        cached_raw = redis_cache.get(_src_key)
        if cached_raw is not None:
            logger.debug("Source cache HIT for Jooble query=%r", keywords)
            data = cached_raw
        else:
            try:
                with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
                    resp = client.post(url, json=payload, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "Jooble API HTTP %s for query=%r: %s",
                    exc.response.status_code,
                    keywords,
                    exc.response.text[:300],
                )
                return []
            except httpx.RequestError as exc:
                logger.error("Jooble API request failed for query=%r: %s", keywords, exc)
                return []
            except Exception as exc:
                logger.error("Unexpected error from Jooble API: %s", exc)
                return []

            # Store raw response for 30 minutes
            redis_cache.set(_src_key, data, ttl_seconds=1800)

        jobs = data.get("jobs", [])
        if not jobs:
            logger.info("Jooble returned 0 jobs for query=%r location=%r", keywords, location)
            return []

        items: list[NormalizedRssItem] = []
        for job in jobs[:limit]:
            item = self._normalize_job(job, keywords)
            if item is not None:
                items.append(item)

        logger.info(
            "Jooble: query=%r location=%r → %d/%d normalized",
            keywords,
            location,
            len(items),
            len(jobs),
        )
        return items

    def fetch_all_default_queries(self) -> list[NormalizedRssItem]:
        """
        Run all DEFAULT_SEARCH_QUERIES and merge results (used by the worker).
        Deduplicates by URL.
        """
        seen_urls: set[str] = set()
        all_items: list[NormalizedRssItem] = []

        for kw, loc in DEFAULT_SEARCH_QUERIES:
            try:
                items = self.fetch_opportunities(keywords=kw, location=loc)
                for item in items:
                    if item.url not in seen_urls:
                        seen_urls.add(item.url)
                        all_items.append(item)
            except Exception as exc:
                logger.error("Jooble query failed (kw=%r): %s", kw, exc)

        logger.info("Jooble total unique items from default queries: %d", len(all_items))
        return all_items

    # ── Private helpers ─────────────────────────────────────────────
    @staticmethod
    def _normalize_job(job: dict, search_keywords: str) -> NormalizedRssItem | None:
        """Map a single Jooble job dict → NormalizedRssItem."""
        title = (job.get("title") or "").strip()
        link = (job.get("link") or "").strip()
        if not title or not link:
            return None

        snippet = (job.get("snippet") or "").strip()
        company = (job.get("company") or "").strip()
        updated_raw = (job.get("updated") or "").strip()
        job_id = job.get("id", "")

        summary = JoobleAdapter._build_summary(job, snippet)
        published_at = JoobleAdapter._parse_date(updated_raw)
        category = JoobleAdapter._infer_category(title, snippet, search_keywords)
        guid = f"jooble:{job_id}" if job_id else f"jooble:{link}"

        return NormalizedRssItem(
            title=title,
            url=link,
            summary=summary,
            published_at=published_at,
            application_deadline=None,
            category=category,
            source_name="Jooble",
            feed_url="jooble-api",
            tags=[kw.strip() for kw in search_keywords.split() if kw.strip()],
            author=company or None,
            guid=guid,
        )

    @staticmethod
    def _build_summary(job: dict, snippet: str) -> str:
        """Assemble a rich summary string from job metadata fields."""
        field_labels = [
            ("company", "Company"),
            ("location", "Location"),
            ("salary", "Salary"),
            ("type", "Type"),
            ("source", "Source"),
        ]
        parts = [
            f"{label}: {val}"
            for key, label in field_labels
            if (val := (job.get(key) or "").strip())
        ]
        if snippet:
            parts.append(snippet)
        return " | ".join(parts)

    @staticmethod
    def _parse_date(raw: str) -> datetime | None:
        """Try to parse the ``updated`` field from Jooble."""
        if not raw:
            return None
        # Jooble typically returns ISO-8601 like "2025-04-15T00:00:00.0000000"
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
        ):
            try:
                # Trim overly long fractional part (Jooble uses 7 digits)
                trimmed = raw[:26]  # "2025-04-15T00:00:00.000000"
                return datetime.strptime(trimmed, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    @staticmethod
    def _infer_category(title: str, snippet: str, search_keywords: str) -> str:
        """Heuristically decide the opportunity category."""
        combined = f"{title} {snippet} {search_keywords}".lower()
        if "intern" in combined:
            return "internship"
        if "freelance" in combined or "contract" in combined:
            return "freelance"
        if "research" in combined or "phd" in combined or "postdoc" in combined:
            return "research"
        return "job"
