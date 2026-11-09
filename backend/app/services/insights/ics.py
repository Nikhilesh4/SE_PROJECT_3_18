"""Minimal RFC 5545 calendar export for application deadlines."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from app.models.rss_item import RssItem


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r", "").replace("\n", "\\n")


def _fold(line: str) -> str:
    """Lines over 75 octets are folded with CRLF + space."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    parts, current = [], b""
    for ch in line:
        enc = ch.encode("utf-8")
        if len(current) + len(enc) > (75 if not parts else 74):
            parts.append(current)
            current = b""
        current += enc
    parts.append(current)
    return "\r\n ".join(p.decode("utf-8") for p in parts)


def _stamp(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_ics(items: Iterable[RssItem], *, calendar_name: str = "UniCompass deadlines") -> str:
    """One VEVENT per posting that has an application deadline, with a reminder 3 days before."""
    now = _stamp(datetime.now(timezone.utc))
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//UniCompass//Deadlines//EN", "CALSCALE:GREGORIAN",
             f"X-WR-CALNAME:{_escape(calendar_name)}"]
    for item in items:
        if item.application_deadline is None:
            continue
        end = item.application_deadline
        lines += [
            "BEGIN:VEVENT",
            f"UID:unicompass-item-{item.id}@unicompass",
            f"DTSTAMP:{now}",
            f"DTSTART:{_stamp(end)}",
            f"DTEND:{_stamp(end)}",
            f"SUMMARY:{_escape('Deadline: ' + item.title)}",
            f"DESCRIPTION:{_escape(item.source_name + ' — ' + item.url)}",
            f"URL:{item.url}",
            "BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{_escape('Closes in 3 days: ' + item.title)}",
            "TRIGGER:-P3D", "END:VALARM",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(l) for l in lines) + "\r\n"
