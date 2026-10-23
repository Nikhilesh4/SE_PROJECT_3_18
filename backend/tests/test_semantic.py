from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.services.matching.semantic import embed_pending_items, embed_pending_profiles
from app.services.rss.cache_service import cache_service
from tests.conftest import make_item

NOW = datetime.now(timezone.utc)


def _embedded_ids(db) -> set[int]:
    with db.connect() as conn:
        rows = conn.execute(text("SELECT id FROM rss_items WHERE embedding IS NOT NULL"))
        return {r[0] for r in rows}


def _seed_ml_and_frontend(seed_items):
    # Frontend item is newer, so it wins any recency tie-break.
    return seed_items(
        make_item(
            url="https://example.com/frontend",
            title="React Frontend Intern",
            summary="Apply now to build UI with CSS and JavaScript.",
            published_at=NOW - timedelta(hours=1),
        ),
        make_item(
            url="https://example.com/ml",
            title="Research Intern, Neural Networks",
            summary="Apply now: train deep learning models with PyTorch.",
            published_at=NOW - timedelta(days=3),
        ),
    )


def test_embed_pending_items_fills_vectors_once(db, seed_items):
    stored = _seed_ml_and_frontend(seed_items)
    assert embed_pending_items() == 2
    assert _embedded_ids(db) == {i.id for i in stored}
    assert embed_pending_items() == 0


def test_semantic_ranking_matches_without_shared_keywords(client, seed_items):
    """'machine learning' shares no keyword with the neural-network posting."""
    frontend, ml = _seed_ml_and_frontend(seed_items)
    embed_pending_items()

    ranked = client.get("/api/feeds/rss?skills=machine learning").json()["items"]
    assert [i["id"] for i in ranked] == [ml.id, frontend.id]


def test_keyword_fallback_when_model_unavailable(client, seed_items, no_embedder):
    frontend, ml = _seed_ml_and_frontend(seed_items)
    assert embed_pending_items() == 0  # nothing to embed with

    ranked = client.get("/api/feeds/rss?skills=machine learning").json()["items"]
    # No keyword hits either way, so recency decides — the feed still works.
    assert [i["id"] for i in ranked] == [frontend.id, ml.id]


def test_semantic_and_keyword_results_use_separate_cache_keys(
    client, seed_items, fake_redis, monkeypatch
):
    _seed_ml_and_frontend(seed_items)
    embed_pending_items()
    client.get("/api/feeds/rss?skills=machine learning")

    from app.services.matching import embeddings

    monkeypatch.setattr(embeddings, "_embedder", None)
    monkeypatch.setattr(embeddings, "_load_failed", True)
    client.get("/api/feeds/rss?skills=machine learning")

    keys = [k for k in fake_redis if k.startswith("feed:")]
    assert len(keys) == 2
    assert sum(k.endswith("-semantic") for k in keys) == 1


def test_upsert_resets_embedding_only_when_text_changes(db, seed_items):
    (item,) = seed_items(make_item(guid="g1"))
    embed_pending_items()

    cache_service.persist_items([make_item(guid="g1")])  # identical re-ingest
    assert _embedded_ids(db) == {item.id}

    cache_service.persist_items([make_item(guid="g1", summary="Apply now. Updated stipend.")])
    assert _embedded_ids(db) == set()


def test_keyword_sort_handles_undated_ties(client, seed_items, no_embedder):
    """Regression: equal scores with a None published_at used to raise TypeError."""
    seed_items(
        make_item(url="https://example.com/dated"),
        make_item(url="https://example.com/undated", published_at=None),
    )
    resp = client.get("/api/feeds/rss?skills=nothing-matches&active_only=false")
    assert resp.status_code == 200
    assert [i["url"] for i in resp.json()["items"]] == [
        "https://example.com/dated",
        "https://example.com/undated",
    ]


def _profile_embedding_is_set(db) -> bool:
    with db.connect() as conn:
        return conn.execute(
            text("SELECT profile_embedding IS NOT NULL FROM profiles")
        ).scalar()


def test_profile_edit_reembeds_inline(client, with_profile, db):
    client.patch("/profile/me", json={"skills": ["PyTorch"]}, headers=with_profile)
    assert _profile_embedding_is_set(db)


def test_profile_embedding_backfilled_by_worker(client, with_profile, db, monkeypatch):
    from app.services.matching import embeddings

    real = embeddings._embedder
    monkeypatch.setattr(embeddings, "_embedder", None)
    client.patch("/profile/me", json={"skills": ["PyTorch"]}, headers=with_profile)
    assert not _profile_embedding_is_set(db)

    monkeypatch.setattr(embeddings, "_embedder", real)
    assert embed_pending_profiles() == 1
    assert _profile_embedding_is_set(db)
