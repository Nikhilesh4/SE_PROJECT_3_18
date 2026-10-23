"""Programmatic entry point for Alembic so the API can migrate on startup."""

from pathlib import Path

from alembic import command
from alembic.config import Config

_BACKEND_DIR = Path(__file__).resolve().parent.parent


def run_migrations(revision: str = "head") -> None:
    """Upgrade the database to `revision` (equivalent to `alembic upgrade head`)."""
    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    command.upgrade(cfg, revision)
