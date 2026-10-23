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

from datetime import datetime, timedelta, timezone  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.db import engine  # noqa: E402
from app.migrations import run_migrations  # noqa: E402
from app.schemas.rss_item import NormalizedRssItem  # noqa: E402
from app.services.redis_cache import redis_cache  # noqa: E402
from app.services.rss.cache_service import cache_service  # noqa: E402


def _reset_schema() -> None:
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))


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


@pytest.fixture
def db(database):
    yield database
    with database.begin() as conn:
        conn.execute(text("TRUNCATE users, rss_items RESTART IDENTITY CASCADE"))


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
