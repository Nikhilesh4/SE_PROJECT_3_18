"""Shared fixtures.

Tests run against a real PostgreSQL (the models use ARRAY and pgvector, which
SQLite cannot emulate). Point TEST_DATABASE_URL at a disposable database whose
name ends in "_test" — the schema is dropped and rebuilt at session start:

    docker run -d --rm --name unicompass-test-pg -p 5433:5432 \
        -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=unicompass_test \
        pgvector/pgvector:pg16
    pytest

Redis is replaced with an in-memory fake, so it does not need to be running.
"""

import os

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/unicompass_test"
)
# Must be set before any app module is imported (settings read env at import).
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["RUN_MIGRATIONS_ON_STARTUP"] = "false"
# A fixed key keeps tests from creating backend/.secret_key; limits are off
# except in tests/test_security.py, which switches them on explicitly.
os.environ["SECRET_KEY"] = "test-secret-key-only-for-the-pytest-suite-0123456789"
os.environ["RATE_LIMIT_ENABLED"] = "false"

import math  # noqa: E402
import re  # noqa: E402
import zlib  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from jose import jwt  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app.migrations import run_migrations  # noqa: E402
from app.repositories.profile_repository import ProfileRepository  # noqa: E402
from app.schemas.profile import ProfileStructured  # noqa: E402
from app.schemas.rss_item import NormalizedRssItem  # noqa: E402
from app.services.matching import embeddings, semantic  # noqa: E402
from app.services.redis_cache import redis_cache  # noqa: E402
from app.services.rss.cache_service import cache_service  # noqa: E402


def _reset_schema() -> None:
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def database():
    if not (make_url(TEST_DATABASE_URL).database or "").endswith("_test"):
        pytest.exit("TEST_DATABASE_URL must name a database ending in '_test'", returncode=2)
    try:
        probe = create_engine(TEST_DATABASE_URL)
        with probe.connect():
            pass
        probe.dispose()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"Test database unavailable ({exc.__class__.__name__}): {TEST_DATABASE_URL}")

    _reset_schema()
    run_migrations()
    yield engine


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    store: dict[str, object] = {}
    monkeypatch.setattr(redis_cache, "get", lambda key: store.get(key))
    monkeypatch.setattr(
        redis_cache, "set", lambda key, value, ttl_seconds: store.__setitem__(key, value) or True
    )
    monkeypatch.setattr(redis_cache, "delete", lambda key: store.pop(key, None) is not None)
    monkeypatch.setattr("app.services.resume_service.publish_profile_updated", lambda user_id: True)
    return store


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    """Background agents fall back to templates; tests never reach a real model."""
    from app.services import llm

    def unavailable():
        raise RuntimeError("no LLM in tests")

    monkeypatch.setattr(llm, "provider_factory", unavailable)


class FakeEmbedder(embeddings.EmbeddingProvider):
    """
    Deterministic stand-in for the real model (no download, no ONNX).

    Words in the same CONCEPTS group share one axis, so "machine learning"
    and "neural networks" are similar without sharing a keyword — the
    property semantic ranking is supposed to add. Other words are hashed
    into the remaining axes, bag-of-words style.
    """

    CONCEPTS = [
        {"machine learning", "neural", "deep learning", "pytorch", "ai"},
        {"frontend", "react", "css", "javascript", "ui"},
        {"finance", "accounting", "banking"},
    ]

    def embed(self, texts):
        return [self._vector(t) for t in texts]

    def _vector(self, text: str) -> list[float]:
        text = text.lower()
        vec = [0.0] * embeddings.EMBEDDING_DIM
        for axis, words in enumerate(self.CONCEPTS):
            vec[axis] += 3.0 * sum(1 for w in words if re.search(rf"\b{w}\b", text))
        for word in re.findall(r"[a-z]+", text):
            vec[len(self.CONCEPTS) + zlib.crc32(word.encode()) % 300] += 0.2
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


@pytest.fixture(autouse=True)
def fake_embedder(monkeypatch):
    """Embeddings are 'ready' by default; set embeddings._embedder = None to test fallback."""
    embedder = FakeEmbedder()
    monkeypatch.setattr(embeddings, "_embedder", embedder)
    monkeypatch.setattr(semantic, "_query_cache", {})
    return embedder


@pytest.fixture
def no_embedder(monkeypatch):
    monkeypatch.setattr(embeddings, "_embedder", None)
    monkeypatch.setattr(embeddings, "_load_failed", True)  # get_embedder() won't try to load


@pytest.fixture
def db(database):
    yield database
    with database.begin() as conn:
        conn.execute(text("TRUNCATE users, rss_items RESTART IDENTITY CASCADE"))


@pytest.fixture(autouse=True)
def _no_email_verification(monkeypatch):
    """Most tests register users directly; test_otp.py turns verification back on."""
    from app.config import settings

    monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", False)


@pytest.fixture
def client(db):
    # Not used as a context manager, so the lifespan (background workers) never starts.
    return TestClient(__import__("app.main", fromlist=["app"]).app)


def register(client: TestClient, email: str = "student@example.com") -> dict:
    resp = client.post(
        "/auth/register",
        json={"name": "Student", "email": email, "password": "s3cret-pass"},
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
def auth_headers(client):
    return register(client)


def make_item(**overrides) -> NormalizedRssItem:
    now = datetime.now(timezone.utc)
    data = dict(
        title="Software Engineering Intern",
        url="https://example.com/jobs/swe-intern",
        summary="Apply now for a paid internship.",
        published_at=now - timedelta(days=1),
        category="internship",
        source_name="Example Board",
        feed_url="https://example.com/feed.xml",
        tags=[],
        guid=None,
    )
    data.update(overrides)
    return NormalizedRssItem(**data)


@pytest.fixture
def seed_items(db):
    """Persist items through the real write path and return them as stored."""

    def _seed(*items: NormalizedRssItem) -> list[NormalizedRssItem]:
        cache_service.persist_items(list(items))
        return [cache_service.get_item(item.guid or item.url) for item in items]

    return _seed


@pytest.fixture
def with_profile(client, auth_headers):
    user_id = _user_id(auth_headers)
    db = SessionLocal()
    try:
        ProfileRepository().upsert_profile(
            db,
            user_id,
            raw_text="resume text",
            parsed_profile=ProfileStructured(skills=["Python", "SQL"], interests=["ML"]),
        )
    finally:
        db.close()
    return auth_headers


def _user_id(headers) -> int:
    token = headers["Authorization"].split()[1]
    return int(jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])["sub"])
