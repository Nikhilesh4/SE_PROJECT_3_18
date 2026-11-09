"""Why a posting ranks for a user, and what skills they are missing for it."""

from __future__ import annotations

import re
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.profile import Profile
from app.models.rss_item import RssItem
from app.repositories.rss_repository import RssItemRepository
from app.services.insights import signals
from app.services.matching.embeddings import get_embedder

_ALIASES = {"js": "javascript", "ts": "typescript", "golang": "go", "k8s": "kubernetes", "ml": "machine learning",
            "dl": "deep learning", "postgres": "postgresql", "node": "node.js", "nextjs": "next.js", "reactjs": "react"}


def canon(skill: str) -> str:
    s = re.sub(r"\s+", " ", skill.strip().lower())
    return _ALIASES.get(s, s)


def user_skills(profile: Profile | None) -> list[str]:
    seen: dict[str, str] = {}
    for s in (profile.parsed_skills or []) if profile else []:
        seen.setdefault(canon(s), s)
    return list(seen.values())


def skill_gap(item: RssItem, skills: Iterable[str]) -> dict:
    """Skills the posting names vs. the user's: matched, missing, and a 0–100 coverage."""
    wanted = signals.extract_skills(f"{item.title}\n{item.summary or ''}\n{' '.join(item.tags or [])}")
    mine = {canon(s) for s in skills}
    matched = [s for s in wanted if canon(s) in mine]
    missing = [s for s in wanted if canon(s) not in mine]
    coverage = round(100 * len(matched) / len(wanted)) if wanted else None
    return {"required": wanted, "matched": matched, "missing": missing, "coverage": coverage}


def explain_ranking(db: Session, item: RssItem, profile: Profile | None) -> dict:
    """Reasons this posting scores for the user: matched words, tags, semantic similarity."""
    skills = user_skills(profile)
    interests = list((profile.parsed_interests or []) if profile else [])
    haystack = f"{item.title}\n{item.summary or ''}".lower()
    tag_text = " ".join(item.tags or []).lower()

    def present(term: str) -> bool:
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(canon(term))}(?![a-z0-9])", haystack + " " + tag_text))

    title_hits = [s for s in skills + interests if re.search(rf"(?<![a-z0-9]){re.escape(canon(s))}(?![a-z0-9])", item.title.lower())]
    body_hits = [s for s in skills + interests if present(s) and s not in title_hits]

    semantic = None
    if profile is not None and profile.profile_embedding is not None and item.embedding is not None and get_embedder(load=False):
        sims = RssItemRepository(db).cosine_similarities([item.id], list(profile.profile_embedding))
        semantic = sims.get(item.id)

    reasons: list[str] = []
    if title_hits:
        reasons.append(f"Title mentions your skills: {', '.join(title_hits)}")
    if body_hits:
        reasons.append(f"Description mentions: {', '.join(body_hits[:6])}")
    if semantic is not None:
        label = "strong" if semantic >= 0.5 else "moderate" if semantic >= 0.3 else "weak"
        reasons.append(f"Semantic similarity to your profile is {label} ({semantic:.2f})")
    if not reasons:
        reasons.append("No direct overlap with your profile; shown because it is recent or in a category you browse")
    return {
        "matched_in_title": title_hits,
        "matched_in_description": body_hits,
        "semantic_similarity": semantic,
        "reasons": reasons,
    }
