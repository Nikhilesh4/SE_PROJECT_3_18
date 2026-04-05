from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func

from app.db import Base

# pgvector import — optional, only used when pgvector extension is installed
try:
    from pgvector.sqlalchemy import Vector

    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False


class Opportunity(Base):
    __tablename__ = "opportunities"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    source = Column(String, nullable=True)  # 'rss', 'adzuna', 'jooble'
    source_url = Column(String, unique=True, nullable=True)
    category = Column(
        String, nullable=True
    )  # 'internship', 'hackathon', 'research', 'course'
    deadline = Column(DateTime(timezone=True), nullable=True)
    embedding = Column(Vector(384), nullable=True) if HAS_PGVECTOR else Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
