"""Split a posting into passages small enough to cite and embed.

Postings are short (summaries are capped at 2,000 characters), so passages
are sentence-packed to ~450 characters with one sentence of overlap: small
enough that a citation points at the relevant part, large enough to keep a
requirement and its context together.
"""

from __future__ import annotations

import html
import re
from typing import Iterable

TARGET_CHARS = 450
MAX_CHARS = 700
OVERLAP_MAX_CHARS = 200  # only short sentences are repeated across passages

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
# Sentence ends, bullets and " - " list separators that feeds flatten into one line.
_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\"'])|\s*[•▪●]\s*|\s+-\s+(?=[A-Z])")


def clean_text(text: str | None) -> str:
    """Feed text can still carry tags and entities such as &#160;."""
    return _WS_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", text or ""))).strip()


def chunk_posting(title: str, tags: Iterable[str], summary: str) -> list[str]:
    """Passages for one posting; always at least one, so every posting is retrievable."""
    passages = _pack(_sentences(clean_text(summary))) or [clean_text(title)]
    tags = [t for t in (clean_text(t) for t in tags) if t]
    if tags:
        passages.append("Tags: " + ", ".join(tags))
    return passages


def _sentences(text: str) -> list[str]:
    parts: list[str] = []
    for sentence in (s.strip() for s in _SPLIT_RE.split(text) if s and s.strip()):
        while len(sentence) > MAX_CHARS:  # run-on text: break at a word boundary
            cut = sentence.rfind(" ", 0, MAX_CHARS)
            cut = cut if cut > 0 else MAX_CHARS
            parts.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if sentence:
            parts.append(sentence)
    return parts


def _pack(sentences: list[str]) -> list[str]:
    passages: list[str] = []
    current: list[str] = []
    length = 0
    for sentence in sentences:
        if current and length + len(sentence) + 1 > TARGET_CHARS:
            passages.append(" ".join(current))
            tail = current[-1]
            current = [tail] if len(tail) <= OVERLAP_MAX_CHARS and len(tail) + len(sentence) < MAX_CHARS else []
            length = sum(len(s) + 1 for s in current)
        current.append(sentence)
        length += len(sentence) + 1
    if current:
        last = " ".join(current)
        # Don't emit a passage that only repeats the previous one's overlap.
        if not passages or not passages[-1].endswith(last):
            passages.append(last)
    return passages
