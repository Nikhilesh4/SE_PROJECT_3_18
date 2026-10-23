"""Drop the unused opportunities table.

Every feed read/write goes through rss_items; the Opportunity model was never
populated. The table is dropped only when it is empty so no data can be lost.

Revision ID: 0002_drop_opportunities
Revises: 0001_baseline
Create Date: 2026-10-24
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0002_drop_opportunities"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("opportunities"):
        return
    if bind.execute(sa.text("SELECT EXISTS (SELECT 1 FROM opportunities)")).scalar():
        return  # unexpected data — leave it for a human to look at
    op.drop_table("opportunities")


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("opportunities"):
        return
    op.create_table(
        "opportunities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("source_url", sa.String(), unique=True, nullable=True),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_opportunities_id", "opportunities", ["id"])
