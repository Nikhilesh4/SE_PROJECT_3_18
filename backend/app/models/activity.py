"""Models for notifications, ranking feedback, missions and agent run traces."""

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, false, true,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.db import Base


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("user_id", "dedupe_key", name="uq_notifications_user_dedupe"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String, nullable=False)  # new_match | deadline | mission | digest
    title = Column(String, nullable=False)
    body = Column(Text, nullable=False, default="")
    rss_item_id = Column(Integer, ForeignKey("rss_items.id", ondelete="CASCADE"), nullable=True)
    dedupe_key = Column(String, nullable=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ItemFeedback(Base):
    __tablename__ = "item_feedback"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    rss_item_id = Column(Integer, ForeignKey("rss_items.id", ondelete="CASCADE"), primary_key=True)
    value = Column(String, nullable=False)  # up | down | hide
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Mission(Base):
    __tablename__ = "missions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    query = Column(Text, nullable=False)
    category = Column(String, nullable=True)
    deadline_after = Column(DateTime(timezone=True), nullable=True)
    remote_only = Column(Boolean, nullable=False, default=False, server_default=false())
    min_stipend = Column(Float, nullable=True)  # INR per month
    active = Column(Boolean, nullable=False, default=True, server_default=true())
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MissionMatch(Base):
    __tablename__ = "mission_matches"

    mission_id = Column(Integer, ForeignKey("missions.id", ondelete="CASCADE"), primary_key=True)
    rss_item_id = Column(Integer, ForeignKey("rss_items.id", ondelete="CASCADE"), primary_key=True)
    score = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AgentRun(Base):
    """Trace of one autonomous agent/pipeline run (what it saw, did and produced)."""

    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    kind = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="running")  # running | ok | error
    input = Column(JSONB, nullable=True)
    output = Column(JSONB, nullable=True)
    steps = Column(JSONB, nullable=False, default=list)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
