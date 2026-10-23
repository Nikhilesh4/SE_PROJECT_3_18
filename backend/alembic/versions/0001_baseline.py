"""Baseline schema: users, profiles, rss_items, bookmarks.

Safe to run against databases created before Alembic was introduced (when
main.py called Base.metadata.create_all and patched tables with raw DDL):
every table is created only if missing, and the old ad-hoc fixes are applied
idempotently.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-10-24
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    if not _has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("email", sa.String(), nullable=False),
            sa.Column("password_hash", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=True),
            sa.Column("skills", sa.ARRAY(sa.String()), nullable=True),
            sa.Column("interests", sa.ARRAY(sa.String()), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_users_id", "users", ["id"])
        op.create_index("ix_users_email", "users", ["email"], unique=True)

    if not _has_table("profiles"):
        op.create_table(
            "profiles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
                unique=True,
            ),
            sa.Column("raw_text", sa.Text(), nullable=True),
            sa.Column("parsed_skills", sa.ARRAY(sa.String()), nullable=True),
            sa.Column("parsed_interests", sa.ARRAY(sa.String()), nullable=True),
            sa.Column("parsed_education", sa.Text(), nullable=True),
            sa.Column("parsed_experience", sa.Text(), nullable=True),
            sa.Column("profile_embedding", Vector(384), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_profiles_id", "profiles", ["id"])

    if not _has_table("rss_items"):
        op.create_table(
            "rss_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("guid", sa.String(), nullable=False),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("url", sa.String(), nullable=False),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("application_deadline", sa.DateTime(timezone=True), nullable=True),
            sa.Column("category", sa.String(), nullable=False),
            sa.Column("source_name", sa.String(), nullable=False),
            sa.Column("feed_url", sa.String(), nullable=False),
            sa.Column("tags", sa.ARRAY(sa.String()), nullable=True),
            sa.Column("author", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_rss_items_id", "rss_items", ["id"])
        op.create_index("ix_rss_items_guid", "rss_items", ["guid"], unique=True)
        op.create_index("ix_rss_items_url", "rss_items", ["url"])
        op.create_index("ix_rss_items_category", "rss_items", ["category"])

    # Formerly patched in main.py for databases that predate the column.
    op.execute(
        "ALTER TABLE rss_items ADD COLUMN IF NOT EXISTS application_deadline TIMESTAMPTZ"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_rss_items_application_deadline "
        "ON rss_items (application_deadline)"
    )

    # Formerly in main.py: an early bookmarks table pointed at opportunities
    # (opportunity_id). Drop it so it is recreated against rss_items.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'bookmarks' AND column_name = 'opportunity_id'
            ) THEN
                DROP TABLE bookmarks;
            END IF;
        END $$;
        """
    )

    if not _has_table("bookmarks"):
        op.create_table(
            "bookmarks",
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                "rss_item_id",
                sa.Integer(),
                sa.ForeignKey("rss_items.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )


def downgrade() -> None:
    op.drop_table("bookmarks")
    op.drop_table("rss_items")
    op.drop_table("profiles")
    op.drop_table("users")
