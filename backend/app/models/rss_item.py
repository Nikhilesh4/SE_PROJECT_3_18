"""SQLAlchemy model for cached RSS feed items."""

from sqlalchemy import Column, Integer, String, Text, DateTime, ARRAY
from sqlalchemy.sql import func

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
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
