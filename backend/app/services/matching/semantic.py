"""Semantic matching service: embeds opportunities/profiles and scores items.

Write side (embedding worker): `embed_pending_items`, `embed_pending_profiles`
fill NULL vectors in batches — covering new rows from every ingestion path,
rows whose text changed (the upsert resets their vector), and backfill.

Read side (feed): `query_vector` embeds the user's skills; similarity itself
is computed by pgvector (`RssItemRepository.cosine_similarities`).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.repositories.profile_repository import ProfileRepository
from app.repositories.rss_repository import RssItemRepository
from app.services.matching.embeddings import (
    get_embedder,
    item_text,
    profile_text,
    query_text,
)
from app.services.rag.indexer import index_rows

logger = logging.getLogger("matching.semantic")

_QUERY_CACHE_MAX = 512
_query_cache: dict[str, list[float]] = {}


# ── Write side ───────────────────────────────────────────────────────────────

def embed_pending_items(batch_size: int = 64, max_items: int = 2000) -> int:
    """Embed rss_items rows with a NULL vector. Returns how many were embedded."""
    embedder = get_embedder()
    if embedder is None:
        return 0

    done = 0
    db = SessionLocal()
    try:
        repo = RssItemRepository(db)
        while done < max_items:
            rows = repo.get_items_missing_embedding(limit=batch_size)
            if not rows:
                break
            vectors = embedder.embed(
                [item_text(r.title, r.tags or [], r.summary or "") for r in rows]
            )
            repo.set_embeddings({r.id: v for r, v in zip(rows, vectors)})
            # New or changed text: rebuild the posting's RAG passages too.
            index_rows(db, rows, embedder)
            done += len(rows)
    finally:
        db.close()
    return done


def embed_pending_profiles(batch_size: int = 32) -> int:
    embedder = get_embedder()
    if embedder is None:
        return 0

    repo = ProfileRepository()
    done = 0
    db = SessionLocal()
    try:
        while True:
            profiles = repo.get_missing_embedding(db, limit=batch_size)
            if not profiles:
                break
            vectors = embedder.embed([_stored_profile_text(p) for p in profiles])
            for profile, vector in zip(profiles, vectors):
                repo.set_embedding(db, profile.id, vector)
            done += len(profiles)
    finally:
        db.close()
    return done


def refresh_profile_embedding(db: Session, profile: Any) -> bool:
    """
    Best-effort inline embedding after a profile write. Never loads the model
    (request path); if it is not ready the worker fills the vector later.
    """
    embedder = get_embedder(load=False)
    if embedder is None:
        return False
    try:
        vector = embedder.embed([_stored_profile_text(profile)])[0]
        ProfileRepository().set_embedding(db, profile.id, vector)
        return True
    except Exception:
        logger.warning("Inline profile embedding failed; worker will retry", exc_info=True)
        db.rollback()
        return False


def _stored_profile_text(profile: Any) -> str:
    experience = [
        f"{e.get('role', '')} at {e.get('company', '')}: {e.get('summary', '')}"
        for e in _json_list(profile.parsed_experience)
    ]
    education = [
        f"{e.get('degree', '')}, {e.get('institution', '')}"
        for e in _json_list(profile.parsed_education)
    ]
    return profile_text(
        profile.parsed_skills or [],
        profile.parsed_interests or [],
        experience,
        education,
    )


def _json_list(raw: Any) -> list[dict]:
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        return []
    return [e for e in parsed or [] if isinstance(e, dict)]


# ── Read side ────────────────────────────────────────────────────────────────

def query_vector(skills: Iterable[str]) -> list[float] | None:
    """Embed a skills list for ranking, or None if the model is not ready."""
    embedder = get_embedder(load=False)
    if embedder is None:
        return None

    key = ",".join(sorted(s.strip().lower() for s in skills if s.strip()))
    if not key:
        return None
    cached = _query_cache.get(key)
    if cached is not None:
        return cached

    try:
        vector = embedder.embed([query_text(key.split(","))])[0]
    except Exception:
        logger.warning("Query embedding failed; using keyword ranking", exc_info=True)
        return None

    if len(_query_cache) >= _QUERY_CACHE_MAX:
        _query_cache.clear()
    _query_cache[key] = vector
    return vector


def item_similarities(item_ids: list[int], vector: list[float]) -> dict[int, float]:
    db = SessionLocal()
    try:
        return RssItemRepository(db).cosine_similarities(item_ids, vector)
    finally:
        db.close()
