"""Map arbitrary feedparser entries into NormalizedRssItem."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol

from app.schemas.rss_item import NormalizedRssItem
from app.services.rss.filter import is_opportunity_post


def strip_html(raw: str | None, max_len: int = 2000) -> str:
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", str(raw))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        text = text[: max_len - 3] + "..."
    return text


def _parse_struct_time(entry: Mapping[str, Any]) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
    return None


def _try_parse_datetime(raw: str) -> datetime | None:
    value = raw.strip()
    formats = (
        "%B %d %Y",
        "%B %d, %Y",
        "%b %d %Y",
        "%b %d, %Y",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%m/%d/%Y",
        "%m-%d-%Y",
        "%d/%m/%y",
        "%d-%m-%y",
        "%m/%d/%y",
        "%m-%d-%y",
    )
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _extract_deadline(entry: Mapping[str, Any], summary_text: str) -> datetime | None:
    # First, honor explicit date-like keys if present in custom feeds.
    for key in ("application_deadline", "deadline", "apply_by", "closing_date"):
        val = entry.get(key)
        if isinstance(val, str):
            parsed = _try_parse_datetime(val)
            if parsed is not None:
                return parsed

    compact = " ".join(summary_text.split())
    match = re.search(
        r"(?:deadline|apply by|last date|application closes?)[:\s-]*"
        r"([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        compact,
        re.IGNORECASE,
    )
    if not match:
        return None
    return _try_parse_datetime(match.group(1))


def _tags(entry: Mapping[str, Any]) -> list[str]:
    raw = entry.get("tags") or []
    out: list[str] = []
    for t in raw:
        if isinstance(t, dict):
            term = t.get("term")
            if term:
                out.append(str(term))
    return out


def _author(entry: Mapping[str, Any]) -> str | None:
    if entry.get("author"):
        return str(entry["author"]).strip() or None
    detail = entry.get("author_detail")
    if isinstance(detail, dict) and detail.get("name"):
        return str(detail["name"]).strip() or None
    return None


class RssEntryNormalizer(Protocol):
    """Implement to customize field extraction per feed or provider."""

    def __call__(
        self,
        entry: Mapping[str, Any],
        *,
        category: str,
        source_name: str,
        feed_url: str,
    ) -> NormalizedRssItem: ...


def default_normalize_entry(
    entry: Mapping[str, Any],
    *,
    category: str,
    source_name: str,
    feed_url: str,
) -> NormalizedRssItem | None:
    title = (entry.get("title") or "").strip()
    link = (entry.get("link") or entry.get("id") or "").strip()
    if not title or not link:
        return None

    # ── Skip RSS-Bridge / aggregator error items ──────────────────────────
    _title_lower = title.lower()
    if any(sig in _title_lower for sig in (
        "bridge returned error",
        "invalid parameters",
        "error 0!",
        "rssbridge error",
    )):
        return None

    summary_raw = entry.get("summary") or entry.get("description") or ""
    # Reject items whose body is a PHP stack trace (RSS Bridge failure)
    if "RssBridge" in summary_raw or "BridgeAbstract" in summary_raw:
        return None

    guid = entry.get("id") or entry.get("guid") or link
    summary = strip_html(summary_raw)

    # ── Content filter: reject articles / recaps, keep only real openings ──
    if not is_opportunity_post(title, summary, category):
        return None

    return NormalizedRssItem(
        title=title,
        url=link,
        summary=summary,
        published_at=_parse_struct_time(entry),
        application_deadline=_extract_deadline(entry, summary),
        category=category,
        source_name=source_name,
        feed_url=feed_url,
        tags=_tags(entry),
        author=_author(entry),
        guid=str(guid) if guid else None,
    )
