"""Add rag_chunks: posting passages for retrieval (hybrid full-text + vector).

Revision ID: 0005_rag_chunks
Revises: 0004_agent_conversations
Create Date: 2026-10-25
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0005_rag_chunks"
down_revision = "0004_agent_conversations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rag_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "rss_item_id",
            sa.Integer(),
            sa.ForeignKey("rss_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("heading", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("rss_item_id", "chunk_index", name="uq_rag_chunks_item_chunk"),
    )
    # Passage text only: if the title were indexed too, every passage of a
    # posting would match its title words, and a full-text hit would no
    # longer mean the passage itself states the fact. (Titles still shape
    # each passage's embedding.)
    op.execute(
        "ALTER TABLE rag_chunks ADD COLUMN tsv tsvector "
        "GENERATED ALWAYS AS (to_tsvector('english', content)) STORED"
    )
    op.create_index("ix_rag_chunks_rss_item_id", "rag_chunks", ["rss_item_id"])
    op.execute("CREATE INDEX ix_rag_chunks_tsv ON rag_chunks USING gin (tsv)")
    op.execute(
        "CREATE INDEX ix_rag_chunks_embedding_hnsw "
        "ON rag_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_table("rag_chunks")
