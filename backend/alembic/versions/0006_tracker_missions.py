"""Application tracker, notifications, feedback, missions, agent runs, discovery metadata.

Revision ID: 0006_tracker_missions
Revises: 0005_rag_chunks
Create Date: 2026-11-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0006_tracker_missions"
down_revision = "0005_rag_chunks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS keeps this safe for databases built from the current models.
    # Application tracker: a bookmark becomes a card on a board.
    for ddl in (
        "ALTER TABLE bookmarks ADD COLUMN IF NOT EXISTS status VARCHAR NOT NULL DEFAULT 'saved'",
        "ALTER TABLE bookmarks ADD COLUMN IF NOT EXISTS notes TEXT",
        "ALTER TABLE bookmarks ADD COLUMN IF NOT EXISTS applied_at TIMESTAMPTZ",
        "ALTER TABLE bookmarks ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now()",
        # Where a posting came from and how far to trust it.
        "ALTER TABLE rss_items ADD COLUMN IF NOT EXISTS discovered_by VARCHAR NOT NULL DEFAULT 'rss'",
        "ALTER TABLE rss_items ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION",
        "ALTER TABLE rss_items ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ",
        "ALTER TABLE rss_items ADD COLUMN IF NOT EXISTS flags VARCHAR[] NOT NULL DEFAULT '{}'",
        "ALTER TABLE rss_items ADD COLUMN IF NOT EXISTS enriched_at TIMESTAMPTZ",
    ):
        op.execute(ddl)

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("rss_item_id", sa.Integer(), sa.ForeignKey("rss_items.id", ondelete="CASCADE"), nullable=True),
        sa.Column("dedupe_key", sa.String(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "dedupe_key", name="uq_notifications_user_dedupe"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id", "id"])

    op.create_table(
        "item_feedback",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("rss_item_id", sa.Integer(), sa.ForeignKey("rss_items.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("value", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "missions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("deadline_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("remote_only", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("min_stipend", sa.Float(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_missions_user_id", "missions", ["user_id"])
    op.create_table(
        "mission_matches",
        sa.Column("mission_id", sa.Integer(), sa.ForeignKey("missions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("rss_item_id", sa.Integer(), sa.ForeignKey("rss_items.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="running"),
        sa.Column("input", JSONB(), nullable=True),
        sa.Column("output", JSONB(), nullable=True),
        sa.Column("steps", JSONB(), nullable=False, server_default="[]"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_runs_kind", "agent_runs", ["kind", "id"])


def downgrade() -> None:
    op.drop_table("agent_runs")
    op.drop_table("mission_matches")
    op.drop_table("missions")
    op.drop_table("item_feedback")
    op.drop_table("notifications")
    for col in ("enriched_at", "flags", "verified_at", "confidence", "discovered_by"):
        op.execute(f"ALTER TABLE rss_items DROP COLUMN IF EXISTS {col}")
    for col in ("updated_at", "applied_at", "notes", "status"):
        op.execute(f"ALTER TABLE bookmarks DROP COLUMN IF EXISTS {col}")
