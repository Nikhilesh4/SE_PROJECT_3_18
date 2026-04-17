"""
AdzunaAdapter
=============
Fetches job/internship listings from the Adzuna REST API and converts them into
the project-standard ``NormalizedRssItem`` format so they flow through the same
pipeline as RSS-sourced opportunities.

API reference: https://api.adzuna.com/v1/api/jobs/{country}/search/{page}

Credentials are read from ``app.config.settings``:
  - ADZUNA_APP_ID
  - ADZUNA_APP_KEY

If either credential is missing the adapter returns an empty list and logs a
warning rather than raising — this keeps the aggregator and background worker
crash-free when the .env file still has placeholder values.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import settings
from app.schemas.rss_item import NormalizedRssItem

logger = logging.getLogger("rss.adzuna")

_BASE_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"

# ------------------------------------------------------------------
# Category keyword → Adzuna "what" search term mappings.
# Adzuna covers jobs and internships well; hackathon/research return
# very thin results so we skip those by default.
# ------------------------------------------------------------------
_CATEGORY_QUERIES: dict[str, str] = {
    "internship": "software intern",
    "job": "software engineer",
}

# Regex to strip HTML tags from Adzuna description snippets.
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(raw: str | None, max_len: int = 1000) -> str:
    if not raw:
        return ""
    text = _HTML_TAG_RE.sub(" ", raw)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


def _parse_adzuna_date(raw: str | None) -> datetime | None:
    """Parse ISO-8601 string returned by Adzuna (e.g. '2024-03-15T12:00:00Z')."""
    if not raw:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def _map_category(label: str | None, requested_category: str) -> str:
    """
    Decide the final category for a listing.  We trust whatever the caller
    asked for (internship / job) but cross-check the Adzuna category label for
    obvious mismatches.
    """
    if requested_category in ("internship", "job"):
        return requested_category
    # Fallback: map Adzuna category labels where possible
    if label:
        lower = label.lower()
        if "intern" in lower:
            return "internship"
    return "job"


def _result_to_item(
    job: dict[str, Any],
    *,
    category: str,
    country: str,
) -> NormalizedRssItem | None:
    """Convert one Adzuna job object to a NormalizedRssItem."""
    title: str = (job.get("title") or "").strip()
    url: str = (job.get("redirect_url") or "").strip()
    if not title or not url:
        return None

    job_id: str = str(job.get("id") or url)

    company_name: str = ""
    company = job.get("company") or {}
    if isinstance(company, dict):
        company_name = (company.get("display_name") or "").strip()

    location_name: str = ""
    location = job.get("location") or {}
    if isinstance(location, dict):
        location_name = (location.get("display_name") or "").strip()

    source_name_parts = ["Adzuna"]
    if company_name:
        source_name_parts.append(company_name)
    if location_name:
        source_name_parts.append(location_name)
    source_name = " — ".join(source_name_parts)

    category_obj = job.get("category") or {}
    adzuna_label: str | None = None
    if isinstance(category_obj, dict):
        adzuna_label = category_obj.get("label")

    tags: list[str] = []
    if adzuna_label:
        tags.append(adzuna_label)

    description = _strip_html(job.get("description"))
    salary_min = job.get("salary_min")
    salary_max = job.get("salary_max")
    if salary_min or salary_max:
        sal_str = f"Salary: {salary_min or '?'} – {salary_max or '?'}"
        description = f"{sal_str}. {description}" if description else sal_str

    return NormalizedRssItem(
        title=title,
        url=url,
        summary=description,
        published_at=_parse_adzuna_date(job.get("created")),
        application_deadline=None,          # Adzuna does not expose this field
        category=_map_category(adzuna_label, category),
        source_name=source_name,
        feed_url=f"https://api.adzuna.com/v1/api/jobs/{country}",
        tags=tags,
        author=company_name or None,
        guid=job_id,
    )


class AdzunaAdapter:
    """
    Adapter that fetches opportunities from the Adzuna API.

    Follows the same public interface pattern as the RSS-based feed ingestion:
    call ``fetch()`` (or ``fetch_for_category()``) and receive a list of
    ``NormalizedRssItem`` objects ready for upsert into the database.

    Usage::

        adapter = AdzunaAdapter()
        items = adapter.fetch_all()              # all configured keyword queries
        items = adapter.fetch(keywords="intern") # custom search
    """

    def __init__(
        self,
        app_id: str | None = None,
        app_key: str | None = None,
    ) -> None:
        self._app_id = app_id or settings.ADZUNA_APP_ID
        self._app_key = app_key or settings.ADZUNA_APP_KEY

    # ------------------------------------------------------------------
    # Primary public methods
    # ------------------------------------------------------------------

    def fetch(
        self,
        keywords: str = "software internship",
        country: str = "gb",
        results_per_page: int = 50,
        page: int = 1,
        category: str = "job",
    ) -> list[NormalizedRssItem]:
        """
        Perform a single Adzuna search and return normalised items.

        Parameters
        ----------
        keywords:
            Search terms passed as the ``what`` query parameter.
        country:
            Adzuna country code (gb, us, in, au, …).
        results_per_page:
            Max results to request (1–50).
        page:
            Results page number (1-indexed).
        category:
            The ``OpportunityCategory`` to tag the results with.
        """
        if not self._app_id or not self._app_key:
            logger.warning(
                "AdzunaAdapter: ADZUNA_APP_ID / ADZUNA_APP_KEY not configured — "
                "skipping Adzuna fetch.  Set them in your .env file."
            )
            return []

        url = _BASE_URL.format(country=country, page=page)
        params: dict[str, Any] = {
            "app_id": self._app_id,
            "app_key": self._app_key,
            "what": keywords,
            "results_per_page": min(max(1, results_per_page), 50),
            "content-type": "application/json",
        }

        try:
            with httpx.Client(timeout=20.0) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data: dict[str, Any] = response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "AdzunaAdapter: HTTP %s for '%s' (country=%s): %s",
                exc.response.status_code,
                keywords,
                country,
                exc,
            )
            return []
        except httpx.RequestError as exc:
            logger.warning("AdzunaAdapter: request error for '%s': %s", keywords, exc)
            return []
        except Exception as exc:  # noqa: BLE001
            logger.error("AdzunaAdapter: unexpected error: %s", exc)
            return []

        results_raw: list[dict[str, Any]] = data.get("results") or []
        items: list[NormalizedRssItem] = []
        for job in results_raw:
            item = _result_to_item(job, category=category, country=country)
            if item is not None:
                items.append(item)

        logger.info(
            "AdzunaAdapter: '%s' (country=%s, page=%d) → %d items",
            keywords,
            country,
            page,
            len(items),
        )
        return items

    def fetch_all(
        self,
        country: str = "gb",
        results_per_page: int = 50,
    ) -> list[NormalizedRssItem]:
        """
        Run all configured keyword queries and deduplicate results by guid.

        This is the method called by ``aggregate_all_feeds`` and the background
        worker so the full Adzuna contribution flows through the same pipeline
        as RSS feeds.
        """
        seen_guids: set[str] = set()
        all_items: list[NormalizedRssItem] = []

        for category, keywords in _CATEGORY_QUERIES.items():
            items = self.fetch(
                keywords=keywords,
                country=country,
                results_per_page=results_per_page,
                category=category,
            )
            for item in items:
                guid = item.guid or item.url
                if guid not in seen_guids:
                    seen_guids.add(guid)
                    all_items.append(item)

        logger.info("AdzunaAdapter.fetch_all → %d unique items total", len(all_items))
        return all_items

    def fetch_for_category(
        self,
        category: str,
        country: str = "gb",
        results_per_page: int = 50,
    ) -> list[NormalizedRssItem]:
        """
        Fetch Adzuna results for a single category keyword.

        Used by the background worker when refreshing only one category at a
        time.  Returns [] for categories Adzuna doesn't support well
        (hackathon, research, freelance).
        """
        keywords = _CATEGORY_QUERIES.get(category)
        if keywords is None:
            logger.debug(
                "AdzunaAdapter: no query configured for category '%s' — skipping.",
                category,
            )
            return []
        return self.fetch(
            keywords=keywords,
            country=country,
            results_per_page=results_per_page,
            category=category,
        )
