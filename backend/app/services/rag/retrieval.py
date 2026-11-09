"""Read side of RAG: hybrid passage retrieval over posting text.

Architecture Patterns Used:
  - Hybrid retrieval: Postgres full-text search (exact terms such as "visa"
    or "stipend") and pgvector similarity (paraphrases such as "paid" vs
    "compensation"), merged with Reciprocal Rank Fusion so neither score
    scale has to be calibrated against the other.

Architecture Tactics:
  - Availability: if the embedding model is not ready, retrieval runs on
    full-text search alone instead of failing.
  - Grounding: every passage carries its posting id, title and URL so the
    answering model can cite it, and weak semantic-only hits are dropped so
    "nothing relevant" stays distinguishable from "something vaguely close".
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Sequence

from app.db import SessionLocal
from app.models.rag_chunk import RagChunk
from app.models.rss_item import RssItem
from app.repositories.rag_repository import ChunkFilter, RagRepository
from app.services.matching.embeddings import get_embedder
from app.services.rag.chunking import clean_text

logger = logging.getLogger("rag.retrieval")

RRF_K = 60  # standard Reciprocal Rank Fusion constant
CANDIDATES_PER_LIST = 40
# all-MiniLM-L6-v2 cosine on the live postings: relevant passages scored
# 0.40–0.50, unrelated ones up to ~0.32.
MIN_SEMANTIC_SIMILARITY = 0.35
MAX_PASSAGES_PER_POSTING = 2  # cross-posting search: show more postings, not one posting's every passage

# Comparison aspects → search terms (OR-ed for full text, joined for embedding).
# Avoid phrases made of stop words plus one generic word: Postgres drops the
# stop words, so "who can apply" would match every "To apply:" line.
ASPECT_TERMS: dict[str, list[str]] = {
    "pay": ["stipend", "salary", "pay", "paid", "compensation", "per month", "unpaid"],
    "location": ["location", "remote", "onsite", "hybrid", "office", "city", "relocation"],
    "skills": ["skills", "requirements", "qualifications", "experience", "proficiency"],
    "eligibility": ["eligibility", "eligible", "students", "undergraduate", "graduates", "degree",
                    "enrolled", "citizens", "authorized"],
    "duration": ["duration", "months", "weeks", "start date", "full-time", "part-time"],
    "deadline": ["deadline", "closing date", "last date", "closes", "due"],
}
DEFAULT_ASPECTS = ["pay", "location", "skills", "eligibility"]


@dataclass
class Passage:
    item_id: int
    chunk_index: int
    text: str
    title: str
    url: str
    category: str
    source: str
    application_deadline: datetime | None
    match: str  # "keyword" | "semantic" | "both" | "context"
    similarity: float | None = None

    def as_dict(self) -> dict:
        return asdict(self)


# ── Public API ───────────────────────────────────────────────────────────────

def search_passages(
    query: str,
    *,
    category: str | None = None,
    active_only: bool = True,
    limit: int = 8,
) -> list[Passage]:
    """Passages across all postings that answer `query`, best first."""
    db = SessionLocal()
    try:
        repo = RagRepository(db)
        fused = _hybrid(
            repo,
            query,
            ChunkFilter(category=category, active_only=active_only),
            min_similarity=MIN_SEMANTIC_SIMILARITY,
            require_all_terms=True,
        )
        per_posting: dict[int, int] = {}
        kept: list[tuple[RagChunk, str, float | None]] = []
        for chunk, match, sim in fused:
            if per_posting.get(chunk.rss_item_id, 0) >= MAX_PASSAGES_PER_POSTING:
                continue
            per_posting[chunk.rss_item_id] = per_posting.get(chunk.rss_item_id, 0) + 1
            kept.append((chunk, match, sim))
            if len(kept) >= limit:
                break
        return _to_passages(repo, kept)
    finally:
        db.close()


def posting_passages(item_id: int, question: str | None = None, *, limit: int = 4) -> list[Passage] | None:
    """
    Passages of one posting, most relevant to `question` first. Postings are
    short, so when retrieval finds fewer than `limit` the remaining passages
    are appended in reading order (match="context"). None if no such posting.
    """
    db = SessionLocal()
    try:
        repo = RagRepository(db)
        item = repo.items_by_id([item_id]).get(item_id)
        if item is None:
            return None
        chunks = repo.chunks_for_items([item_id])
        if not chunks:  # not indexed yet (the worker runs every minute)
            return [_passage(item, -1, _item_text(item), "context", None)]

        ranked = (
            _hybrid(repo, question, ChunkFilter(item_ids=[item_id]), min_similarity=0.0)
            if question and question.strip()
            else []
        )
        picked = ranked[:limit]
        seen = {c.id for c, _, _ in picked}
        for chunk in chunks:
            if len(picked) >= limit:
                break
            if chunk.id not in seen:
                picked.append((chunk, "context", None))
        return _to_passages(repo, picked)
    finally:
        db.close()


def compare_postings(item_ids: Sequence[int], aspects: Sequence[str] | None = None) -> dict:
    """
    Side-by-side facts for 2–5 postings: metadata plus, for each aspect, the
    passage of each posting that best addresses it (None when nothing does).
    """
    aspects = [a.strip().lower() for a in (aspects or DEFAULT_ASPECTS) if a.strip()]
    db = SessionLocal()
    try:
        repo = RagRepository(db)
        items = repo.items_by_id(item_ids)
        postings = []
        for item_id in item_ids:
            item = items.get(item_id)
            if item is None:
                postings.append({"id": item_id, "error": "Opportunity not found."})
                continue
            facts: dict[str, dict | None] = {}
            for aspect in aspects:
                terms = ASPECT_TERMS.get(aspect, [aspect])
                best = _hybrid(
                    repo,
                    " ".join(terms),
                    ChunkFilter(item_ids=[item_id]),
                    min_similarity=MIN_SEMANTIC_SIMILARITY,
                    keyword_terms=terms,
                )
                facts[aspect] = (
                    {"text": best[0][0].content, "chunk_index": best[0][0].chunk_index, "match": best[0][1]}
                    if best
                    else None
                )
            postings.append(
                {
                    "id": item.id,
                    "title": clean_text(item.title),
                    "url": item.url,
                    "category": item.category,
                    "source": item.source_name,
                    "published_at": item.published_at,
                    "application_deadline": item.application_deadline,
                    "tags": (item.tags or [])[:10],
                    "aspects": facts,
                }
            )
        return {"aspects": aspects, "postings": postings}
    finally:
        db.close()


# ── Internals ────────────────────────────────────────────────────────────────

def embed_query(text: str) -> list[float] | None:
    """Embed free text on a request path, or None if the model is not ready."""
    embedder = get_embedder(load=False)
    if embedder is None or not text.strip():
        return None
    try:
        return embedder.embed([text.strip()])[0]
    except Exception:
        logger.warning("Query embedding failed; using full-text search only", exc_info=True)
        return None


def _hybrid(
    repo: RagRepository,
    query: str,
    filters: ChunkFilter,
    *,
    min_similarity: float,
    keyword_terms: Sequence[str] | None = None,
    require_all_terms: bool = False,
) -> list[tuple[RagChunk, str, float | None]]:
    """
    Fuse full-text and vector rankings: [(chunk, match kind, similarity)], best first.

    Across all postings a full-text hit must contain every term (OR-ing them
    let "quantum computing" match any passage saying "computer"). Within one
    posting the candidates are already relevant, so any term will do.
    """
    terms = list(keyword_terms or _terms(query))
    tsquery = " ".join(_quote(t) for t in terms) if require_all_terms else _or_query(terms)
    keyword_hits = repo.keyword_search(tsquery or '""', filters, CANDIDATES_PER_LIST)
    vector = embed_query(query)
    vector_hits = (
        repo.vector_search(vector, filters, CANDIDATES_PER_LIST) if vector is not None else []
    )

    scores: dict[int, float] = {}
    chunks: dict[int, RagChunk] = {}
    kinds: dict[int, set[str]] = {}
    sims: dict[int, float] = {}
    for rank, (chunk, _) in enumerate(keyword_hits):
        scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (RRF_K + rank + 1)
        chunks[chunk.id] = chunk
        kinds.setdefault(chunk.id, set()).add("keyword")
    for rank, (chunk, sim) in enumerate(vector_hits):
        sims[chunk.id] = sim
        if sim < min_similarity and chunk.id not in chunks:
            continue  # too weak to stand on its own
        scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (RRF_K + rank + 1)
        chunks[chunk.id] = chunk
        kinds.setdefault(chunk.id, set()).add("semantic")

    ordered = sorted(scores, key=lambda cid: (-scores[cid], cid))
    return [
        (
            chunks[cid],
            "both" if len(kinds[cid]) == 2 else next(iter(kinds[cid])),
            round(sims[cid], 4) if cid in sims else None,
        )
        for cid in ordered
    ]


_TOKEN_RE = re.compile(r'"[^"]+"|[\w+#.\-]+')
_STOP = {
    "a", "an", "the", "is", "are", "am", "do", "does", "did", "i", "me", "my", "it", "this",
    "that", "to", "of", "in", "on", "for", "and", "or", "with", "as", "be", "can", "what",
    "which", "who", "how", "there", "any", "at", "by", "you", "your", "they", "we",
}


def _terms(query: str) -> list[str]:
    tokens = [t.strip(".-") if not t.startswith('"') else t for t in _TOKEN_RE.findall(query or "")]
    return [t for t in tokens if t and t.lower() not in _STOP]


def _or_query(terms: Sequence[str]) -> str:
    """
    Questions rarely contain every word of the answer, so terms are OR-ed;
    ts_rank_cd still ranks passages matching more of them higher.
    """
    return " OR ".join(_quote(t) for t in terms) or '""'


def _quote(term: str) -> str:
    return term if term.startswith('"') or " " not in term else f'"{term}"'


def _to_passages(
    repo: RagRepository, picked: list[tuple[RagChunk, str, float | None]]
) -> list[Passage]:
    items = repo.items_by_id({c.rss_item_id for c, _, _ in picked})
    return [
        _passage(items[c.rss_item_id], c.chunk_index, c.content, match, sim)
        for c, match, sim in picked
        if c.rss_item_id in items
    ]


def _passage(item: RssItem, chunk_index: int, text: str, match: str, sim: float | None) -> Passage:
    return Passage(
        item_id=item.id,
        chunk_index=chunk_index,
        text=text,
        title=clean_text(item.title),
        url=item.url,
        category=item.category,
        source=item.source_name,
        application_deadline=item.application_deadline,
        match=match,
        similarity=sim,
    )


def _item_text(item: RssItem) -> str:
    return clean_text(item.summary) or clean_text(item.title)
