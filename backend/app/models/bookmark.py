"""SQLAlchemy model for user bookmarks on RSS feed items (also the application tracker card)."""

from sqlalchemy import Column, Integer, ForeignKey, DateTime, String, Text
from sqlalchemy.sql import func

from app.db import Base

# Kanban columns, in board order.
APPLICATION_STATUSES = ("saved", "applied", "interview", "offer", "rejected")


class Bookmark(Base):
    __tablename__ = "bookmarks"

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    rss_item_id = Column(
        Integer, ForeignKey("rss_items.id", ondelete="CASCADE"), primary_key=True
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String, nullable=False, default="saved", server_default="saved")
    notes = Column(Text, nullable=True)
    applied_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
