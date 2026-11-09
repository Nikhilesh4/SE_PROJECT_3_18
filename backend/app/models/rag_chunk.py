"""SQLAlchemy model for posting passages used by RAG retrieval."""

from sqlalchemy import Column, Computed, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from app.db import Base


class RagChunk(Base):
    __tablename__ = "rag_chunks"

    id = Column(Integer, primary_key=True)
    rss_item_id = Column(
        Integer, ForeignKey("rss_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index = Column(Integer, nullable=False)
    heading = Column(String, nullable=False)  # the posting title, for context
    content = Column(Text, nullable=False)
    # all-MiniLM-L6-v2 embedding of "heading. content"
    embedding = Column(Vector(384), nullable=False)
    # Maintained by Postgres (alembic 0005); never written by the app.
    tsv = Column(TSVECTOR, Computed("to_tsvector('english', content)", persisted=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
