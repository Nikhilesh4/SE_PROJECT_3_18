"""SQLAlchemy model for cached RSS feed items."""

from sqlalchemy import Column, Integer, String, Text, DateTime, ARRAY, Float
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from app.db import Base


class RssItem(Base):
    __tablename__ = "rss_items"

    id = Column(Integer, primary_key=True, index=True)
    guid = Column(String, unique=True, nullable=False, index=True)
    title = Column(String, nullable=False)
    url = Column(String, nullable=False, index=True)
    summary = Column(Text, nullable=True, default="")
    published_at = Column(DateTime(timezone=True), nullable=True)
    application_deadline = Column(DateTime(timezone=True), nullable=True, index=True)
    category = Column(String, nullable=False, index=True)
    source_name = Column(String, nullable=False)
    feed_url = Column(String, nullable=False)
    tags = Column(ARRAY(String), default=[])
    author = Column(String, nullable=True)
    # all-MiniLM-L6-v2 embedding of title/tags/summary; filled asynchronously
    # by the embedding worker and reset to NULL when that text changes.
    embedding = Column(Vector(384), nullable=True)
    # Provenance: which channel found it, how sure we are it is a real opening,
    # when a verifier last checked it, and any warning flags (e.g. "scam-risk").
    discovered_by = Column(String, nullable=False, default="rss", server_default="rss")
    confidence = Column(Float, nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    flags = Column(ARRAY(String), nullable=False, default=list, server_default="{}")
    enriched_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
