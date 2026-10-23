"""Compass Agent API — chat with an AI assistant that can use UniCompass tools.

POST /agent/chat streams Server-Sent Events, one JSON object per `data:` line:
  {"type": "conversation", "id", "title"}   first event
  {"type": "text", "delta"}                  answer text as it is generated
  {"type": "tool_call", "id", "name", "arguments"}
  {"type": "tool_result", "id", "name", "ok", "preview"}
  {"type": "notice" | "error", "message"}
  {"type": "done", "stop"}                   last event
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal, get_db
from app.middleware.auth import get_current_user, oauth2_scheme
from app.models.user import User
from app.repositories.agent_repository import AgentRepository
from app.services.agent.loop import run_agent
from app.services.agent.providers import LLMProvider, ProviderError, get_provider
from app.services.agent.tools import Toolbox

logger = logging.getLogger("agent.router")

router = APIRouter(prefix="/agent", tags=["agent"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: int | None = None


def provider_for(name: str | None = None) -> LLMProvider:
    """Indirection so tests can substitute a scripted provider."""
    return get_provider(name)


def _sse(event: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(event, default=str)}\n\n".encode()


@router.post("/chat")
async def chat(
    body: ChatRequest,
    request: Request,
    user: User = Depends(get_current_user),
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    repo = AgentRepository(db)
    if body.conversation_id is not None:
        conversation = repo.get_conversation(user_id=user.id, conversation_id=body.conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        if repo.count_messages(conversation.id) >= settings.AGENT_MAX_MESSAGES_PER_CONVERSATION:
            raise HTTPException(status_code=409, detail="This chat is full. Start a new one.")
        provider_name, model = conversation.provider, conversation.model
    else:
        conversation = None
        provider_name, model = settings.AGENT_PROVIDER, None

    try:
        provider = provider_for(provider_name)
        if model:
            provider.model = model  # a conversation stays on the model that started it
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if conversation is None:
        conversation = repo.create_conversation(
            user_id=user.id,
            title=_title(body.message),
            provider=provider.name,
            model=provider.model,
        )
    conversation_id, title = conversation.id, conversation.title
    history = repo.messages(conversation_id)

    async def events() -> AsyncIterator[bytes]:
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

        async def emit(event: dict[str, Any]) -> None:
            await queue.put(event)

        async def worker() -> None:
            # Own session: the request-scoped one may close before streaming ends.
            session = SessionLocal()
            try:
                store = AgentRepository(session)
                async with Toolbox(request.app, token) as toolbox:
                    stop = await run_agent(
                        provider=provider,
                        toolbox=toolbox,
                        history=history,
                        user_text=body.message,
                        emit=emit,
                        persist=lambda msgs: store.append(conversation_id, msgs),
                        max_tool_rounds=settings.AGENT_MAX_TOOL_ROUNDS,
                    )
                await emit({"type": "done", "stop": stop})
            except Exception:
                logger.exception("Agent run failed")
                await emit({"type": "error", "message": "Something went wrong. Please try again."})
                await emit({"type": "done", "stop": "error"})
            finally:
                session.close()
                await queue.put(None)

        yield _sse({"type": "conversation", "id": conversation_id, "title": title})
        task = asyncio.create_task(worker())
        try:
            while (event := await queue.get()) is not None:
                yield _sse(event)
        finally:
            if not task.done():  # client disconnected
                task.cancel()

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/conversations")
def list_conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [
        {"id": c.id, "title": c.title, "provider": c.provider, "updated_at": c.updated_at}
        for c in AgentRepository(db).list_conversations(user_id=user.id)
    ]


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    repo = AgentRepository(db)
    conversation = repo.get_conversation(user_id=user.id, conversation_id=conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    try:
        provider = provider_for(conversation.provider)
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    visible = [v for m in repo.messages(conversation.id) if (v := provider.visible(m))]
    return {"id": conversation.id, "title": conversation.title, "messages": _merge_turns(visible)}


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    repo = AgentRepository(db)
    conversation = repo.get_conversation(user_id=user.id, conversation_id=conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    repo.delete_conversation(conversation)
    return {"deleted": conversation_id}


def _title(message: str) -> str:
    line = " ".join(message.split())
    return line if len(line) <= 60 else line[:57].rsplit(" ", 1)[0] + "…"


def _merge_turns(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fold consecutive assistant messages (tool rounds) into one chat bubble."""
    merged: list[dict[str, Any]] = []
    for m in messages:
        if merged and m["role"] == "assistant" and merged[-1]["role"] == "assistant":
            prev = merged[-1]
            prev["text"] = "\n\n".join(t for t in (prev["text"], m["text"]) if t)
            prev["tool_calls"] = prev["tool_calls"] + m["tool_calls"]
        else:
            merged.append({**m, "tool_calls": list(m["tool_calls"])})
    return merged
