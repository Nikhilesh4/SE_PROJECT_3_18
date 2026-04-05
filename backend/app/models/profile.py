from sqlalchemy import Column, Integer, String, Text, ARRAY, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.db import Base

try:
    from pgvector.sqlalchemy import Vector

    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    raw_text = Column(Text, nullable=True)
    parsed_skills = Column(ARRAY(String), default=[])
    parsed_education = Column(Text, nullable=True)
    parsed_experience = Column(Text, nullable=True)
    profile_embedding = (
        Column(Vector(384), nullable=True)
        if HAS_PGVECTOR
        else Column(Text, nullable=True)
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
