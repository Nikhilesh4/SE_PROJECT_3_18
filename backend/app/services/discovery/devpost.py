"""Devpost hackathons (public JSON listing used by the site's own front end)."""

from __future__ import annotations

import logging
import re

import httpx

from app.schemas.rss_item import NormalizedRssItem
from app.services.adapters.base_adapter import OpportunityAdapter
from app.services.discovery.textutil import parse_date_range_end

logger = logging.getLogger("discovery.devpost")
URL = "https://devpost.com/api/hackathons"


def parse_hackathons(payload: dict) -> list[NormalizedRssItem]:
    out = []
    for h in payload.get("hackathons", []):
        if not h.get("url") or not h.get("title"):
            continue
        themes = [t.get("name", "") for t in h.get("themes", [])]
        prize = re.sub(r"<[^>]+>", "", h.get("prize_amount") or "").strip()
        loc = (h.get("displayed_location") or {}).get("location", "")
        dates = h.get("submission_period_dates", "")
        out.append(NormalizedRssItem(
            title=h["title"],
            url=h["url"].split("?")[0],
            summary=f"Hackathon hosted by {h.get('organization_name', 'Devpost')}. {loc}. Submission period: {dates}. "
                    f"Prizes: {prize or 'see page'}. Themes: {', '.join(themes)}. {h.get('time_left_to_submission', '')}.",
            application_deadline=parse_date_range_end(dates),
            category="hackathon",
            source_name="Devpost",
            feed_url=URL,
            tags=["devpost", *themes[:4]],
            author=h.get("organization_name"),
            guid=f"devpost:{h.get('id')}",
            discovered_by="devpost",
            confidence=0.9,
        ))
    return out


class DevpostAdapter(OpportunityAdapter):
    def __init__(self, *, client: httpx.Client | None = None, pages: int = 2) -> None:
        self._client, self._pages = client, pages

    def fetch_opportunities(self, *, keywords: str = "", location: str = "", page: int = 1, limit: int = 20) -> list[NormalizedRssItem]:
        client = self._client or httpx.Client(headers={"User-Agent": "UniCompass/1.0"})
        out: list[NormalizedRssItem] = []
        try:
            for p in range(1, self._pages + 1):
                resp = client.get(URL, params={"status[]": "open", "order_by": "deadline", "page": p, "per_page": 30}, timeout=20)
                resp.raise_for_status()
                out.extend(parse_hackathons(resp.json()))
        finally:
            if self._client is None:
                client.close()
        return out
