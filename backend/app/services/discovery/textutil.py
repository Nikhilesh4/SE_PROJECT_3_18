"""HTML → text and small parsing helpers shared by the discovery adapters."""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone

_TAG_BLOCK = re.compile(r"<(script|style|noscript|svg|head)[\s\S]*?</\1>", re.I)
_BREAKS = re.compile(r"<\s*(br|p|/p|/div|/li|/h[1-6]|/tr)\b[^>]*>", re.I)
_TAGS = re.compile(r"<[^>]+>")


def html_to_text(raw: str, *, max_chars: int = 0) -> str:
    """Strip tags/scripts, decode entities (twice: some APIs double-escape), collapse whitespace."""
    if not raw:
        return ""
    text = raw
    if "&lt;" in text and "<" not in text:  # Greenhouse returns escaped HTML
        text = html.unescape(text)
    text = _TAG_BLOCK.sub(" ", text)
    text = _BREAKS.sub("\n", text)
    text = _TAGS.sub(" ", text)
    text = html.unescape(text).replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:max_chars].rstrip() if max_chars else text


def parse_iso(value: str | int | float | None) -> datetime | None:
    """ISO-8601 strings and epoch seconds/milliseconds → aware UTC datetime."""
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
            number = float(value)
            if number > 1e11:
                number /= 1000
            return datetime.fromtimestamp(number, tz=timezone.utc)
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None


_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def parse_date_range_end(text: str) -> datetime | None:
    """'Oct 01 - Nov 12, 2026' → 2026-11-12 (the end of the range)."""
    m = re.search(r"([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2})(?:,?\s+(20\d\d))?\s*$", text.strip())
    if not m or m.group(1).lower() not in _MONTHS:
        return None
    year = m.group(3)
    if not year:
        y = re.search(r"(20\d\d)", text)
        year = y.group(1) if y else str(datetime.now(timezone.utc).year)
    try:
        return datetime(int(year), _MONTHS[m.group(1).lower()], int(m.group(2)), 23, 59, tzinfo=timezone.utc)
    except ValueError:
        return None


def json_ld_job_postings(page_html: str) -> list[dict]:
    """JobPosting objects from <script type="application/ld+json"> blocks."""
    found: list[dict] = []
    for block in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>', page_html, re.I):
        try:
            data = json.loads(block.strip())
        except json.JSONDecodeError:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                if "@graph" in node:
                    stack.extend(node["@graph"])
                kind = node.get("@type")
                if kind == "JobPosting" or (isinstance(kind, list) and "JobPosting" in kind):
                    found.append(node)
    return found


EARLY_CAREER = re.compile(
    r"\b(intern(ship)?s?|co-?op|apprentice(ship)?|new[- ]?grad(uate)?s?|graduate|junior|entry[- ]level|trainee|"
    r"student|fellow(ship)?|early[- ]career|campus|sde[- ]?1|software engineer i\b|research assistant)\b",
    re.I,
)


def is_early_career(title: str, extra: str = "") -> bool:
    return bool(EARLY_CAREER.search(f"{title} {extra}"))


def classify(title: str, text: str = "") -> str:
    """Map a posting to one of the app's categories from its title (and a bit of body)."""
    t = title.lower()
    if re.search(r"\b(intern(ship)?s?|co-?op|apprentice|trainee)\b", t):
        return "internship"
    if re.search(r"\b(research|scientist|phd|fellow)\b", t):
        return "research"
    if re.search(r"hackathon|challenge|competition", t):
        return "hackathon"
    if re.search(r"\b(freelance|contract|contractor)\b", t):
        return "freelance"
    return "job"
