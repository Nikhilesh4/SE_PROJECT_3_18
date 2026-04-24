"""
Shared pytest fixtures for end-to-end testing.

Uses SQLite in-memory database with type adapters for PostgreSQL-specific
types (ARRAY, Vector). All tests run fully offline — no PostgreSQL, Redis,
or external API dependencies needed.

Key technique: Register a custom SQLite type compiler for ARRAY that
emits TEXT, and a type-level adapter that serializes lists to/from JSON.
We build a test FastAPI app that skips app.main's module-level DB init.
"""

from __future__ import annotations

import json
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# ── Step 1: Register SQLite type compiler for ARRAY ─────────────────────────
# Must happen BEFORE any table metadata is compiled against SQLite.
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
from sqlalchemy.sql.sqltypes import ARRAY

# Teach SQLite how to render ARRAY → TEXT
_orig_visit = getattr(SQLiteTypeCompiler, "visit_ARRAY", None)

def _visit_ARRAY_sqlite(self, type_, **kw):
    return "TEXT"

SQLiteTypeCompiler.visit_ARRAY = _visit_ARRAY_sqlite


# ── Step 2: Patch ARRAY to serialize lists as JSON for SQLite ────────────────
_orig_bind = ARRAY.bind_processor
_orig_result = ARRAY.result_processor


def _array_bind_processor(self, dialect):
    if dialect.name == "sqlite":
        def process(value):
            if value is None:
                return None
            return json.dumps(value)
        return process
    if _orig_bind:
        return _orig_bind(self, dialect)
    return None


def _array_result_processor(self, dialect, coltype):
    if dialect.name == "sqlite":
        def process(value):
            if value is None:
                return None
            if isinstance(value, list):
                return value
            return json.loads(value)
        return process
    if _orig_result:
        return _orig_result(self, dialect, coltype)
    return None


ARRAY.bind_processor = _array_bind_processor
ARRAY.result_processor = _array_result_processor


# ── Step 3: Handle pgvector Vector type ──────────────────────────────────────
# Ensure Profile model's Vector column compiles to TEXT in SQLite.
try:
    from pgvector.sqlalchemy import Vector
    from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler as _STC

    def _visit_Vector_sqlite(self, type_, **kw):
        return "TEXT"

    _STC.visit_VECTOR = _visit_Vector_sqlite
    _STC.visit_Vector = _visit_Vector_sqlite
    # Also patch bind/result for Vector
    _orig_v_bind = getattr(Vector, "bind_processor", None)
    _orig_v_result = getattr(Vector, "result_processor", None)

    def _vector_bind_processor(self, dialect):
        if dialect.name == "sqlite":
            def process(value):
                if value is None:
                    return None
                return json.dumps(value) if isinstance(value, list) else str(value)
            return process
        if _orig_v_bind:
            return _orig_v_bind(self, dialect)
        return None

    def _vector_result_processor(self, dialect, coltype):
        if dialect.name == "sqlite":
            def process(value):
                if value is None:
                    return None
                try:
                    return json.loads(value) if isinstance(value, str) else value
                except (json.JSONDecodeError, TypeError):
                    return value
            return process
        if _orig_v_result:
            return _orig_v_result(self, dialect, coltype)
        return None

    Vector.bind_processor = _vector_bind_processor
    Vector.result_processor = _vector_result_processor
except ImportError:
    pass  # pgvector not installed — Profile model will use TEXT fallback


# ── Now safe to import app models ────────────────────────────────────────────
from app.db import Base, get_db
from app.models.user import User
from app.models.rss_item import RssItem
from app.models.bookmark import Bookmark
from app.models.profile import Profile
from app.models.notification import Notification


# ── In-memory SQLite engine ──────────────────────────────────────────────────
SQLALCHEMY_TEST_DATABASE_URL = "sqlite://"

test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(test_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=test_engine
)


# ── In-memory Redis stub ────────────────────────────────────────────────────

class FakeRedisCache:
    """Minimal in-memory cache that mirrors RedisCacheService's interface."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def get(self, key: str) -> Any | None:
        return self._store.get(key)

    def set(self, key: str, value: Any, ttl_seconds: int = 0) -> bool:
        self._store[key] = value
        return True

    def delete(self, key: str) -> bool:
        self._store.pop(key, None)
        return True

    def delete_pattern(self, pattern: str) -> int:
        import fnmatch
        to_delete = [k for k in self._store if fnmatch.fnmatch(k, pattern)]
        for k in to_delete:
            del self._store[k]
        return len(to_delete)

    def is_available(self) -> bool:
        return True


fake_redis = FakeRedisCache()


# ── Build test app (avoid app.main's module-level DB operations) ─────────

def _build_test_app() -> FastAPI:
    """
    Construct a test FastAPI app with the same routers as production,
    but without the module-level PostgreSQL DDL in app.main.
    """
    from app.routers import auth, bookmark, feeds, notifications, profile

    @asynccontextmanager
    async def test_lifespan(_: FastAPI):
        yield

    app = FastAPI(title="UniCompass API (Test)", lifespan=test_lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router)
    app.include_router(bookmark.router, prefix="/api")
    app.include_router(feeds.router, prefix="/api")
    app.include_router(profile.router)
    app.include_router(notifications.router)

    @app.get("/")
    def root():
        return {"message": "UniCompass API is running"}

    @app.get("/health")
    def health_check():
        return {"status": "healthy"}

    return app


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _patch_redis():
    """Replace the real Redis cache with our in-memory stub globally."""
    with patch("app.services.redis_cache.redis_cache", fake_redis), \
         patch("app.routers.feeds.redis_cache", fake_redis), \
         patch("app.routers.profile.redis_cache", fake_redis):
        fake_redis._store.clear()
        yield


@pytest.fixture(autouse=True)
def _patch_events():
    """Prevent real Redis pub/sub and event bus side-effects."""
    with patch("app.services.events._subscribers", {}):
        yield


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    """Provide a clean database session for each test."""
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient wired to the test DB session."""
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app = _build_test_app()
    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app) as tc:
        yield tc

    app.dependency_overrides.clear()


# ── Helper fixtures ──────────────────────────────────────────────────────────

@pytest.fixture()
def test_user(db_session: Session) -> tuple:
    """Create a test user in the DB and return (user_obj, jwt_token)."""
    from passlib.context import CryptContext
    from app.middleware.auth import create_access_token

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    user = User(
        name="Test User",
        email="test@example.com",
        password_hash=pwd_context.hash("testpass123"),
        skills=["python", "react"],
        interests=["machine learning"],
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token(data={"sub": str(user.id)})
    return user, token


@pytest.fixture()
def second_user(db_session: Session) -> tuple:
    """Create a second test user for multi-user isolation tests."""
    from passlib.context import CryptContext
    from app.middleware.auth import create_access_token

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    user = User(
        name="Second User",
        email="second@example.com",
        password_hash=pwd_context.hash("secondpass"),
        skills=["java", "spring"],
        interests=["devops"],
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token(data={"sub": str(user.id)})
    return user, token


@pytest.fixture()
def sample_rss_items(db_session: Session) -> list:
    """Seed the DB with a few RSS items for feed/bookmark tests."""
    now = datetime.now(timezone.utc)
    items = []
    for i in range(5):
        item = RssItem(
            guid=f"guid-{i}",
            title=f"Test Opportunity {i} — Python Developer",
            url=f"https://example.com/opp/{i}",
            summary=f"An exciting opportunity #{i} for Python and React developers.",
            published_at=now,
            category="job" if i % 2 == 0 else "internship",
            source_name="TestFeed",
            feed_url="https://example.com/feed.xml",
            tags=["python", "react"] if i % 2 == 0 else ["java", "spring"],
            author="TestAuthor",
        )
        db_session.add(item)
        items.append(item)
    db_session.commit()
    for item in items:
        db_session.refresh(item)
    return items


@pytest.fixture()
def auth_headers(test_user: tuple) -> dict[str, str]:
    """Convenience: return Authorization header dict."""
    _, token = test_user
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def second_auth_headers(second_user: tuple) -> dict[str, str]:
    """Authorization headers for the second user."""
    _, token = second_user
    return {"Authorization": f"Bearer {token}"}
