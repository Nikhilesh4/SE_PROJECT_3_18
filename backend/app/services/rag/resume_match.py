"""Resume ↔ posting retrieval: which lines of a student's resume best support
an application to one posting.

Evidence units are the resume's own bullets (from the uploaded PDF text), so
projects and achievements count even though the parsed profile only keeps
experience and education. Profiles without stored text fall back to the
parsed experience entries.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.db import SessionLocal
from app.models.profile import Profile
from app.repositories.rag_repository import RagRepository
from app.services.matching.embeddings import get_embedder
from app.services.rag.chunking import chunk_posting, clean_text

MIN_UNIT_CHARS = 30
MAX_UNIT_CHARS = 400
MAX_UNITS = 150

_BULLET_RE = re.compile(r"^\s*[•●▪◦‣*\-–]\s*")
_WORD_RE = re.compile(r"[a-z0-9+#]+")


def resume_units(raw_text: str | None, experience_json: Any = None) -> list[str]:
    """Split resume text into bullet-sized units (PDF lines wrap mid-bullet)."""
    units: list[str] = []
    current = ""

    def flush() -> None:
        nonlocal current
        text = " ".join(current.split())
        if len(text) >= MIN_UNIT_CHARS and text not in units:
            units.append(text[:MAX_UNIT_CHARS])
        current = ""

    for line in (raw_text or "").splitlines():
        stripped = line.strip()
        if not stripped or (stripped.isupper() and len(stripped) < 40):
            flush()  # blank line or a section heading such as "EXPERIENCE"
        elif _BULLET_RE.match(line):
            flush()
            current = _BULLET_RE.sub("", line)
        elif current and current.rstrip().endswith((".", ";", ":")):
            flush()
            current = stripped
        else:
            current = f"{current} {stripped}" if current else stripped
    flush()

    if not units:
        units = [
            u
            for u in (
                clean_text(f"{e.get('role', '')} at {e.get('company', '')}: {e.get('summary', '')}")
                for e in _json_list(experience_json)
            )
            if len(u) >= MIN_UNIT_CHARS
        ]
    return units[:MAX_UNITS]


def match_resume(profile: Profile, item_id: int, *, limit: int = 6) -> dict | None:
    """Resume evidence for one posting, best first. None if the posting doesn't exist."""
    db = SessionLocal()
    try:
        item = RagRepository(db).items_by_id([item_id]).get(item_id)
    finally:
        db.close()
    if item is None:
        return None

    posting_text = clean_text(f"{item.title}. {' '.join(item.tags or [])}. {item.summary or ''}")
    posting_words = set(_WORD_RE.findall(posting_text.lower()))
    skills = profile.parsed_skills or []
    matched = [s for s in skills if _mentions(posting_text, s)]
    skill_words = {w for s in skills for w in _WORD_RE.findall(s.lower())}
    unmatched_tags = [
        t for t in (item.tags or []) if not set(_WORD_RE.findall(t.lower())) <= skill_words
    ]

    units = resume_units(profile.raw_text, profile.parsed_experience)
    passages = chunk_posting(item.title, item.tags or [], item.summary or "")
    embedder = get_embedder(load=False)
    evidence: list[dict] = []
    ranked_by = "keyword"
    if units and embedder is not None:
        ranked_by = "semantic"
        vectors = embedder.embed([*units, *passages])
        unit_vecs, passage_vecs = vectors[: len(units)], vectors[len(units):]
        for text, uv in zip(units, unit_vecs):
            sims = [sum(a * b for a, b in zip(uv, pv)) for pv in passage_vecs]  # normalised → cosine
            best = max(range(len(sims)), key=sims.__getitem__)
            evidence.append(
                {"text": text, "similarity": round(sims[best], 4), "best_posting_passage": passages[best]}
            )
        evidence.sort(key=lambda e: -e["similarity"])
    elif units:
        for text in units:
            overlap = len(set(_WORD_RE.findall(text.lower())) & posting_words)
            evidence.append({"text": text, "shared_words": overlap})
        evidence.sort(key=lambda e: -e["shared_words"])

    return {
        "item_id": item.id,
        "title": clean_text(item.title),
        "ranked_by": ranked_by,
        "matched_skills": matched,
        "posting_tags_not_in_profile": unmatched_tags,
        "evidence": evidence[:limit],
    }


def _mentions(text: str, skill: str) -> bool:
    skill = skill.strip()
    if not skill:
        return False
    return re.search(rf"(?<![\w+#]){re.escape(skill)}(?![\w+#])", text, re.IGNORECASE) is not None


def _json_list(raw: Any) -> list[dict]:
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        return []
    return [e for e in parsed or [] if isinstance(e, dict)]
