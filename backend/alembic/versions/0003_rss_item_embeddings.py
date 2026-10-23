"""Add rss_items.embedding for semantic matching, with an HNSW cosine index.

Revision ID: 0003_rss_item_embeddings
Revises: 0002_drop_opportunities
Create Date: 2026-10-24
"""
from alembic import op

revision = "0003_rss_item_embeddings"
down_revision = "0002_drop_opportunities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE rss_items ADD COLUMN IF NOT EXISTS embedding vector(384)")
    # HNSW gives fast approximate top-k for "nearest opportunities" queries
    # (notifications, RAG). Feed ranking scores a filtered id set directly.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_rss_items_embedding_hnsw "
        "ON rss_items USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_rss_items_embedding_hnsw")
    op.execute("ALTER TABLE rss_items DROP COLUMN IF EXISTS embedding")
