"""Source Scout: proposes new RSS feeds for admin approval.

Given a site URL it finds feed links (`<link rel="alternate">` plus common paths),
validates each by parsing it, and measures how many entries pass the same content
filter the live ingestion uses. A proposal is only ever *stored*; nothing is
ingested until an admin approves it (approval appends to approved_feeds.json).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from urllib.parse import urljoin

import feedparser

from app.services.discovery import fetcher
from app.services.rss.feed_sources import APPROVED_FEEDS_PATH, FEED_SOURCES, load_approved_feeds
from app.services.rss.filter import is_opportunity_post

COMMON_PATHS = ("/feed", "/rss", "/feed.xml", "/rss.xml", "/atom.xml", "/index.xml", "/careers/feed")
_LINK_RE = re.compile(r"<link[^>]+type=[\"']application/(?:rss|atom)\+xml[\"'][^>]*>", re.I)
_HREF_RE = re.compile(r"href=[\"']([^\"']+)[\"']", re.I)
MIN_ENTRIES = 3
MIN_PASS_RATE = 0.3


@dataclass
class Proposal:
    url: str
    title: str
    entries: int
    pass_rate: float
    suggested_category: str
    sample_titles: list[str]
    already_configured: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


def find_feed_urls(site_url: str, html: str) -> list[str]:
    found = [urljoin(site_url, m.group(1)) for tag in _LINK_RE.findall(html) if (m := _HREF_RE.search(tag))]
    found += [urljoin(site_url, p) for p in COMMON_PATHS]
    return list(dict.fromkeys(found))


def _category_for(titles: list[str], default: str = "job") -> str:
    text = " ".join(titles).lower()
    for cat, pattern in (("hackathon", r"hackathon"), ("internship", r"intern"), ("research", r"research|phd|postdoc|fellowship"),
                         ("freelance", r"freelanc|contract"), ("course", r"course|learn")):
        if re.search(pattern, text):
            return cat
    return default


def evaluate_feed(url: str, body: str) -> Proposal | None:
    parsed = feedparser.parse(body)
    entries = parsed.entries
    if len(entries) < MIN_ENTRIES:
        return None
    titles = [e.get("title", "") for e in entries[:30]]
    category = _category_for(titles)
    passing = [t for e, t in zip(entries[:30], titles) if is_opportunity_post(t, e.get("summary", ""), category)]
    rate = len(passing) / max(len(titles), 1)
    if rate < MIN_PASS_RATE:
        return None
    known = {s.url for s in FEED_SOURCES}
    return Proposal(url, parsed.feed.get("title") or url, len(entries), round(rate, 2), category, passing[:5], url in known)


def scout_site(site_url: str, *, fetch=fetcher.fetch_page) -> list[Proposal]:
    """Candidate feeds on a site that look like real opportunity listings. Raises FetchBlocked for unsafe URLs."""
    page = fetch(site_url)
    proposals: list[Proposal] = []
    for feed_url in find_feed_urls(page.url, page.text if page.status < 400 else "")[:8]:
        try:
            resp = fetch(feed_url)
        except fetcher.FetchBlocked:
            continue
        except Exception:
            continue
        if resp.status >= 400:
            continue
        proposal = evaluate_feed(feed_url, resp.text)
        if proposal:
            proposals.append(proposal)
    return proposals


def approve(url: str, category: str, source_name: str) -> None:
    """Append an approved feed (idempotent). Takes effect when the app/worker next starts."""
    existing = [{"url": s.url, "category": s.category, "source_name": s.source_name} for s in load_approved_feeds()]
    if any(e["url"] == url for e in existing):
        return
    existing.append({"url": url, "category": category, "source_name": source_name[:80]})
    APPROVED_FEEDS_PATH.write_text(json.dumps(existing, indent=2))
