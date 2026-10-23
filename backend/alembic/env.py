"""Alembic environment — runs migrations against settings.DATABASE_URL.

Invoked both from the CLI (`alembic upgrade head`) and programmatically by
app.migrations.run_migrations() during API startup.
"""

from alembic import context
from sqlalchemy import create_engine, pool

from app.config import settings
from app.db import Base
import app.models  # noqa: F401 — registers every table on Base.metadata

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(settings.DATABASE_URL, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
