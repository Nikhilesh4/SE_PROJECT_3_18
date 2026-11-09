"""ATS career boards: public JSON job APIs, no scraping, no keys.

Greenhouse, Lever, Ashby, Workable and SmartRecruiters all publish each
customer's open roles at a documented URL. The watchlist
(`ats_watchlist.json`) says which company boards to read; by default only
early-career roles (interns, new grads, juniors …) are kept so a company with
2,000 openings doesn't bury the feed.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx

from app.config import settings
from app.schemas.rss_item import NormalizedRssItem
from app.services.adapters.base_adapter import OpportunityAdapter
from app.services.discovery.textutil import classify, html_to_text, is_early_career, parse_iso

logger = logging.getLogger("discovery.ats")

VENDORS = ("greenhouse", "lever", "ashby", "workable", "smartrecruiters")
CONFIDENCE = 0.95
SUMMARY_CHARS = 2000


def load_watchlist(path: str | None = None) -> list[dict]:
    p = Path(path or settings.ATS_WATCHLIST_PATH)
    try:
        entries = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        logger.warning("ATS watchlist unreadable at %s", p)
        return []
    return [e for e in entries if isinstance(e, dict) and e.get("vendor") in VENDORS and e.get("token") and not e.get("disabled")]


def _item(*, vendor: str, company: str, title: str, url: str, summary: str, published, location: str, feed_url: str, jid: str, tags=None) -> NormalizedRssItem:
    title = " ".join(title.split())
    loc = f" ({location})" if location else ""
    return NormalizedRssItem(
        title=f"{title} — {company}{loc}" if company else title,
        url=url,
        summary=summary[:SUMMARY_CHARS],
        published_at=published,
        category=classify(title),
        source_name=f"{company} careers" if company else vendor,
        feed_url=feed_url,
        tags=[t for t in [vendor, *(tags or [])] if t],
        author=company or None,
        guid=f"ats:{vendor}:{jid}",
        discovered_by=f"ats:{vendor}",
        confidence=CONFIDENCE,
    )


# ── Per-vendor parsers (pure: payload → items) ───────────────────────────────

def parse_greenhouse(payload: dict, token: str, company: str) -> list[NormalizedRssItem]:
    feed = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
    out = []
    for j in payload.get("jobs", []):
        out.append(_item(
            vendor="greenhouse", company=j.get("company_name") or company, title=j.get("title", ""), url=j.get("absolute_url", ""),
            summary=html_to_text(j.get("content", "")), published=parse_iso(j.get("first_published") or j.get("updated_at")),
            location=(j.get("location") or {}).get("name", ""), feed_url=feed, jid=str(j.get("id")),
            tags=[d.get("name", "") for d in j.get("departments", [])[:2]],
        ))
    return out


def parse_lever(payload: list, token: str, company: str) -> list[NormalizedRssItem]:
    feed = f"https://api.lever.co/v0/postings/{token}"
    out = []
    for j in payload if isinstance(payload, list) else []:
        cats = j.get("categories") or {}
        remote = " remote" if j.get("workplaceType") == "remote" else ""
        out.append(_item(
            vendor="lever", company=company, title=j.get("text", ""), url=j.get("hostedUrl", ""),
            summary=(j.get("descriptionPlain") or html_to_text(j.get("description", ""))) + remote, published=parse_iso(j.get("createdAt")),
            location=cats.get("location", ""), feed_url=feed, jid=str(j.get("id")), tags=[cats.get("team", ""), cats.get("commitment", "")],
        ))
    return out


def parse_ashby(payload: dict, token: str, company: str) -> list[NormalizedRssItem]:
    feed = f"https://api.ashbyhq.com/posting-api/job-board/{token}"
    out = []
    for j in payload.get("jobs", []):
        if j.get("isListed") is False:
            continue
        comp = ((j.get("compensation") or {}).get("compensationTierSummary")) or ""
        summary = (j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml", "")))
        if j.get("isRemote"):
            summary = "Remote. " + summary
        if comp:
            summary = f"Compensation: {comp}. " + summary
        out.append(_item(
            vendor="ashby", company=company, title=j.get("title", ""), url=j.get("jobUrl", ""), summary=summary,
            published=parse_iso(j.get("publishedAt")), location=j.get("location", ""), feed_url=feed, jid=str(j.get("id")),
            tags=[j.get("department", ""), j.get("team", "")],
        ))
    return out


def parse_workable(payload: dict, token: str, company: str) -> list[NormalizedRssItem]:
    feed = f"https://apply.workable.com/api/v1/widget/accounts/{token}"
    out = []
    for j in payload.get("jobs", []):
        loc = ", ".join(x for x in (j.get("city"), j.get("country")) if x)
        out.append(_item(
            vendor="workable", company=payload.get("name") or company, title=j.get("title", ""), url=j.get("url") or j.get("shortlink", ""),
            summary=html_to_text(j.get("description", "")), published=parse_iso(j.get("published_on") or j.get("created_at")),
            location=loc, feed_url=feed, jid=str(j.get("shortcode") or j.get("id")), tags=[j.get("department", "")],
        ))
    return out


def parse_smartrecruiters(payload: dict, token: str, company: str) -> list[NormalizedRssItem]:
    feed = f"https://api.smartrecruiters.com/v1/companies/{token}/postings"
    out = []
    for j in payload.get("content", []):
        loc = j.get("location") or {}
        place = ", ".join(x for x in (loc.get("city"), loc.get("country", "").upper()) if x)
        summary = f"{j.get('name', '')}. " + ("Remote. " if loc.get("remote") else "") + f"Department: {(j.get('department') or {}).get('label', '')}. Type: {(j.get('typeOfEmployment') or {}).get('label', '')}."
        out.append(_item(
            vendor="smartrecruiters", company=(j.get("company") or {}).get("name") or company, title=j.get("name", ""),
            url=f"https://jobs.smartrecruiters.com/{token}/{j.get('id')}", summary=summary, published=parse_iso(j.get("releasedDate")),
            location=place, feed_url=feed, jid=str(j.get("id")), tags=[(j.get("function") or {}).get("label", "")],
        ))
    return out


_ENDPOINTS = {
    "greenhouse": ("https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true", parse_greenhouse),
    "lever": ("https://api.lever.co/v0/postings/{token}?mode=json", parse_lever),
    "ashby": ("https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true", parse_ashby),
    "workable": ("https://apply.workable.com/api/v1/widget/accounts/{token}?details=true", parse_workable),
    "smartrecruiters": ("https://api.smartrecruiters.com/v1/companies/{token}/postings?limit=100", parse_smartrecruiters),
}


class ATSAdapter(OpportunityAdapter):
    def __init__(self, watchlist: list[dict] | None = None, *, early_career_only: bool = True, client: httpx.Client | None = None) -> None:
        self._watchlist = watchlist if watchlist is not None else load_watchlist()
        self._early_only = early_career_only
        self._client = client

    def fetch_board(self, vendor: str, token: str, company: str = "") -> list[NormalizedRssItem]:
        url, parser = _ENDPOINTS[vendor]
        client = self._client or httpx.Client(timeout=25, headers={"User-Agent": "UniCompass/1.0"})
        try:
            resp = client.get(url.format(token=token))
            resp.raise_for_status()
            items = parser(resp.json(), token, company)
        finally:
            if self._client is None:
                client.close()
        items = [i for i in items if i.url and i.title]
        if self._early_only:
            items = [i for i in items if is_early_career(i.title)]
        return items

    def fetch_opportunities(self, *, keywords: str = "", location: str = "", page: int = 1, limit: int = 20) -> list[NormalizedRssItem]:
        out: list[NormalizedRssItem] = []
        for entry in self._watchlist:
            try:
                out.extend(self.fetch_board(entry["vendor"], entry["token"], entry.get("name", "")))
            except Exception as exc:  # one dead board must not stop the rest
                logger.warning("ATS %s/%s failed: %s", entry["vendor"], entry["token"], exc)
        return out
