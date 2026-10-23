"""Data access for Compass Agent conversations (append-only message log)."""

from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.agent import AgentConversation, AgentMessage


class AgentRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create_conversation(
        self, *, user_id: int, title: str, provider: str, model: str
    ) -> AgentConversation:
        conversation = AgentConversation(
            user_id=user_id, title=title, provider=provider, model=model
        )
        self._db.add(conversation)
        self._db.commit()
        self._db.refresh(conversation)
        return conversation

    def get_conversation(self, *, user_id: int, conversation_id: int) -> AgentConversation | None:
        return (
            self._db.query(AgentConversation)
            .filter(
                AgentConversation.id == conversation_id,
                AgentConversation.user_id == user_id,
            )
            .first()
        )

    def list_conversations(self, *, user_id: int, limit: int = 50) -> Sequence[AgentConversation]:
        return (
            self._db.query(AgentConversation)
            .filter(AgentConversation.user_id == user_id)
            .order_by(AgentConversation.updated_at.desc())
            .limit(limit)
            .all()
        )

    def delete_conversation(self, conversation: AgentConversation) -> None:
        self._db.delete(conversation)
        self._db.commit()

    def messages(self, conversation_id: int) -> list[dict[str, Any]]:
        rows = (
            self._db.query(AgentMessage.message)
            .filter(AgentMessage.conversation_id == conversation_id)
            .order_by(AgentMessage.seq)
            .all()
        )
        return [r[0] for r in rows]

    def count_messages(self, conversation_id: int) -> int:
        return (
            self._db.query(func.count(AgentMessage.id))
            .filter(AgentMessage.conversation_id == conversation_id)
            .scalar()
            or 0
        )

    def append(self, conversation_id: int, messages: list[dict[str, Any]]) -> None:
        """Append messages in order. Never rewrites earlier history."""
        if not messages:
            return
        next_seq = (
            self._db.query(func.coalesce(func.max(AgentMessage.seq), -1))
            .filter(AgentMessage.conversation_id == conversation_id)
            .scalar()
            + 1
        )
        for offset, message in enumerate(messages):
            self._db.add(
                AgentMessage(conversation_id=conversation_id, seq=next_seq + offset, message=message)
            )
        self._db.query(AgentConversation).filter(AgentConversation.id == conversation_id).update(
            {AgentConversation.updated_at: func.now()}, synchronize_session=False
        )
        self._db.commit()
