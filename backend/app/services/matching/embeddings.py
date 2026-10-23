"""Text embeddings for semantic matching (FR-4).

Architecture Patterns Used:
  - Adapter: EmbeddingProvider hides the embedding runtime (fastembed today)
    behind one `embed()` call, so the model or runtime can be swapped.
  - Lazy Singleton: the model is loaded once, on first use, in a background
    thread (the embedding worker warms it at startup).

Architecture Tactics:
  - Availability: request paths call `get_embedder(load=False)` and never
    block on a model download; if the model is not ready (or failed to
    load), callers fall back to keyword-only ranking.
"""

from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from typing import Iterable, Sequence

from app.config import settings

logger = logging.getLogger("matching.embeddings")

# Must match the vector(384) columns (alembic 0001 / 0003).
EMBEDDING_DIM = 384


class EmbeddingProvider(ABC):
    """Turns texts into L2-normalised vectors of length EMBEDDING_DIM."""

    @abstractmethod
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        ...


class FastEmbedProvider(EmbeddingProvider):
    def __init__(self, model_name: str, cache_dir: str) -> None:
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name, cache_dir=cache_dir)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._model.embed(list(texts))]


_embedder: EmbeddingProvider | None = None
_load_failed = False
_lock = threading.Lock()


def get_embedder(*, load: bool = True) -> EmbeddingProvider | None:
    """
    Return the shared provider, or None when embeddings are unavailable.

    load=False never triggers a (possibly slow, network-bound) model load —
    use it on request paths.
    """
    global _embedder, _load_failed
    if _embedder is not None or not load:
        return _embedder
    if not settings.EMBEDDINGS_ENABLED or _load_failed:
        return None

    with _lock:
        if _embedder is None and not _load_failed:
            try:
                provider = FastEmbedProvider(
                    settings.EMBEDDING_MODEL, settings.EMBEDDING_CACHE_DIR
                )
                dim = len(provider.embed(["dimension probe"])[0])
                if dim != EMBEDDING_DIM:
                    raise ValueError(
                        f"{settings.EMBEDDING_MODEL} produces {dim}-dim vectors, "
                        f"expected {EMBEDDING_DIM}"
                    )
                _embedder = provider
                logger.info("Embedding model ready: %s", settings.EMBEDDING_MODEL)
            except Exception:
                _load_failed = True
                logger.exception(
                    "Embedding model failed to load — falling back to keyword ranking"
                )
    return _embedder


# ── Text builders: what each kind of record "means" for matching ─────────────
# Kept deliberately plain. On a labelled sample of postings, labels such as
# "Skills and interests:" or "Category:" pulled unrelated postings closer to
# every query (worst-case good-vs-bad margin 0.20 → 0.11 for the query label).

def item_text(title: str, tags: Iterable[str], summary: str) -> str:
    parts = [title.strip()]
    tags = [t for t in tags if t]
    if tags:
        parts.append(", ".join(tags))
    if summary:
        parts.append(summary.strip()[:1000])
    return ". ".join(parts)


def query_text(skills: Iterable[str]) -> str:
    return ", ".join(s.strip() for s in skills if s.strip())


def profile_text(
    skills: Iterable[str],
    interests: Iterable[str],
    experience: Iterable[str] = (),
    education: Iterable[str] = (),
) -> str:
    parts = [query_text([*skills, *interests])]
    parts.extend(e for e in experience if e)
    parts.extend(e for e in education if e)
    return ". ".join(p for p in parts if p)[:2000]
