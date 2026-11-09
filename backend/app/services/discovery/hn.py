"""Hacker News "Ask HN: Who is hiring?" — many startup and remote roles that never reach an RSS feed.

Uses the HN Algolia API. Each top-level comment is one company's posting; by
convention the first line reads `Company | Role | Location | REMOTE | ...`.
A heuristic parser handles that format; an optional LLM extractor (see
pipeline.Extractor) can be layered on for free-form comments.
"""

from __future__ import annotations

import logging
import re

import httpx

from app.schemas.rss_item import NormalizedRssItem
from app.services.adapters.base_adapter import OpportunityAdapter
from app.services.discovery.textutil import classify, html_to_text, is_early_career, parse_iso

logger = logging.getLogger("discovery.hn")

ALGOLIA = "https://hn.algolia.com/api/v1"
CONFIDENCE = 0.7
_ROLE_RE = re.compile(
    r"engineer|developer|intern\b|internship|scientist|designer|manager|analyst|researcher|research|sde|devops|sre\b|data\b|\bml\b|full[- ]?stack|"
    r"front[- ]?end|back[- ]?end|lead\b|consultant|architect|phd|postdoc|founding|head of|product|marketing|sales|operations|roles?\b|hiring|apprentice|co-?op",
    re.I)
_LOCATION_RE = re.compile(r"remote|onsite|on-site|hybrid|[A-Z][a-z]+,? ?[A-Z]{2}\b|india|usa|\buk\b|europe|berlin|london|bangalore|bengaluru|new york|\bsf\b|san francisco|worldwide", re.I)
_LOCATION_ONLY = re.compile(r"(remote|onsite|on-site|hybrid|full[- ]?time|part[- ]?time)( .*)?", re.I)
_URL_RE = re.compile(r"https?://[^\s<>\"')]+")


def parse_comment(comment: dict) -> NormalizedRssItem | None:
    raw = comment.get("text")
    if not raw or comment.get("author") is None:
        return None
    text = html_to_text(raw)
    first_line = text.split("\n", 1)[0]
    parts = [p.strip() for p in first_line.split("|")]
    if len(parts) < 2 or len(first_line) > 300:
        return None  # not in the conventional format
    company, rest = parts[0], parts[1:]
    role = next((p for p in rest if _ROLE_RE.search(p) and not _LOCATION_ONLY.fullmatch(p.strip())), None)
    if role is None or not company or company.lower().startswith("http"):
        return None
    location = next((p for p in rest if p != role and _LOCATION_RE.search(p)), "")
    cid = str(comment.get("id") or comment.get("objectID"))
    apply_url = next((u for u in _URL_RE.findall(raw.replace("&#x2F;", "/").replace("&amp;", "&")) if "ycombinator.com" not in u), None)
    return NormalizedRssItem(
        title=f"{role} — {company}" + (f" ({location})" if location else ""),
        url=f"https://news.ycombinator.com/item?id={cid}",
        summary=(("Apply: " + apply_url + "\n") if apply_url else "") + text[:1900],
        published_at=parse_iso(comment.get("created_at")),
        category=classify(role),
        source_name="HN Who's Hiring",
        feed_url=f"{ALGOLIA}/items",
        tags=["hn", "startup"],
        author=company,
        guid=f"hn:{cid}",
        discovered_by="hn_whoishiring",
        confidence=CONFIDENCE,
    )


class HNHiringAdapter(OpportunityAdapter):
    def __init__(self, *, client: httpx.Client | None = None, early_career_only: bool = True, max_items: int = 150) -> None:
        self._client = client
        self._early = early_career_only
        self._max = max_items

    def _get(self, client: httpx.Client, path: str, **params) -> dict:
        resp = client.get(f"{ALGOLIA}/{path}", params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def latest_thread_id(self, client: httpx.Client) -> str | None:
        hits = self._get(client, "search_by_date", query="Ask HN: Who is hiring?", tags="story,author_whoishiring", hitsPerPage=5)["hits"]
        for h in hits:
            if (h.get("title") or "").lower().startswith("ask hn: who is hiring"):
                return h["objectID"]
        return None

    def fetch_opportunities(self, *, keywords: str = "", location: str = "", page: int = 1, limit: int = 20) -> list[NormalizedRssItem]:
        client = self._client or httpx.Client(headers={"User-Agent": "UniCompass/1.0"})
        try:
            thread = self.latest_thread_id(client)
            if not thread:
                return []
            data = self._get(client, f"items/{thread}")
        finally:
            if self._client is None:
                client.close()
        items = []
        for child in data.get("children", []):
            item = parse_comment(child)
            if item is None:
                continue
            if self._early and not is_early_career(item.title, item.summary[:600]) and not re.search(r"all levels|any level|new grads?", item.summary, re.I):
                continue
            items.append(item)
            if len(items) >= self._max:
                break
        return items
