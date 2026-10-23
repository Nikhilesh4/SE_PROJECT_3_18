"""Alembic baseline must adopt databases created by the old create_all startup."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from app.db import Base
from app.migrations import run_migrations
from tests.conftest import _reset_schema


def _head() -> str:
    cfg = Config()
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    return ScriptDirectory.from_config(cfg).get_current_head()


def test_upgrade_adopts_legacy_schema(database):
    try:
        _reset_schema()
        with database.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            # What main.py used to produce: tables from create_all, plus the
            # unused opportunities table, minus the later-added deadline column.
            Base.metadata.create_all(conn)
            conn.execute(text("ALTER TABLE rss_items DROP COLUMN application_deadline"))
            conn.execute(text("ALTER TABLE rss_items DROP COLUMN embedding"))
            conn.execute(text("CREATE TABLE opportunities (id SERIAL PRIMARY KEY, title VARCHAR)"))

        run_migrations()

        insp = inspect(database)
        assert "opportunities" not in insp.get_table_names()
        columns = {c["name"] for c in insp.get_columns("rss_items")}
        assert {"application_deadline", "embedding"} <= columns
        with database.connect() as conn:
            version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert version == _head()

        run_migrations()  # idempotent
    finally:
        _reset_schema()
        run_migrations()


def test_non_empty_opportunities_table_is_kept(database):
    try:
        _reset_schema()
        with database.begin() as conn:
            conn.execute(text("CREATE TABLE opportunities (id SERIAL PRIMARY KEY, title VARCHAR)"))
            conn.execute(text("INSERT INTO opportunities (title) VALUES ('keep me')"))

        run_migrations()
        assert "opportunities" in inspect(database).get_table_names()
    finally:
        _reset_schema()
        run_migrations()
