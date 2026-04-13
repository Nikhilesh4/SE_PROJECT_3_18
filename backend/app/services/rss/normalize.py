"""Map arbitrary feedparser entries into NormalizedRssItem."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol

from app.schemas.rss_item import NormalizedRssItem


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
    summary_raw = entry.get("summary") or entry.get("description") or ""
    guid = entry.get("id") or entry.get("guid") or link
    return NormalizedRssItem(
        title=title,
        url=link,
        summary=strip_html(summary_raw),
        published_at=_parse_struct_time(entry),
        category=category,
        source_name=source_name,
        feed_url=feed_url,
        tags=_tags(entry),
        author=_author(entry),
        guid=str(guid) if guid else None,
    )
