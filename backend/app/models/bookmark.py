"""SQLAlchemy model for user bookmarks on RSS feed items."""

from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.sql import func

from app.db import Base


class Bookmark(Base):
    __tablename__ = "bookmarks"

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    rss_item_id = Column(
        Integer, ForeignKey("rss_items.id", ondelete="CASCADE"), primary_key=True
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
