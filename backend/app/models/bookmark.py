from sqlalchemy import Column, Integer, ForeignKey
from app.db import Base


class Bookmark(Base):
    __tablename__ = "bookmarks"

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    opportunity_id = Column(
        Integer, ForeignKey("opportunities.id", ondelete="CASCADE"), primary_key=True
    )
