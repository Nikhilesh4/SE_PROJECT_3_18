"""RAG API: retrieve cited passages from posting text, and grounded answers.

Retrieval endpoints return passages, not prose: callers that already have a
model (the Compass Agent, MCP clients) write the answer themselves. Only
POST /items/{id}/ask runs a model, for the posting page's Ask box.

  GET  /api/rag/search?q=                 passages across all postings
  GET  /api/rag/items/{id}/passages?q=    passages of one posting
  GET  /api/rag/compare?ids=1,2,3         per-aspect passages side by side
  GET  /api/rag/items/{id}/resume-match   resume lines that support an application (auth)
  POST /api/rag/items/{id}/ask            grounded, cited answer (auth)
"""

from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.repositories.profile_repository import ProfileRepository
from app.services.agent.providers import LLMProvider, ProviderError, get_provider
from app.services.rag import retrieval
from app.services.rag.answer import answer_question
from app.services.rag.resume_match import match_resume

router = APIRouter(prefix="/rag", tags=["rag"])

MAX_COMPARE = 5


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)


def provider_for() -> LLMProvider:
    """Indirection so tests can substitute a scripted provider."""
    return get_provider()


@router.get("/search")
def search(
    q: str = Query(..., min_length=2, max_length=300),
    category: Optional[str] = Query(None),
    active_only: bool = Query(True),
    limit: int = Query(8, ge=1, le=25),
) -> dict:
    passages = retrieval.search_passages(q, category=category, active_only=active_only, limit=limit)
    return {"query": q, "passages": [p.as_dict() for p in passages]}


@router.get("/items/{item_id}/passages")
def item_passages(
    item_id: int,
    q: Optional[str] = Query(None, max_length=300),
    limit: int = Query(4, ge=1, le=10),
) -> dict:
    passages = retrieval.posting_passages(item_id, q, limit=limit)
    if passages is None:
        raise HTTPException(status_code=404, detail="Opportunity not found.")
    return {"item_id": item_id, "query": q, "passages": [p.as_dict() for p in passages]}


@router.get("/compare")
def compare(
    ids: str = Query(..., description="Comma-separated opportunity ids (2–5)"),
    aspects: Optional[str] = Query(
        None, description="Comma-separated, e.g. pay,location,skills,eligibility,duration,deadline"
    ),
) -> dict:
    try:
        item_ids = list(dict.fromkeys(int(part) for part in ids.split(",") if part.strip()))
    except ValueError:
        raise HTTPException(status_code=422, detail="ids must be comma-separated integers.")
    if not 2 <= len(item_ids) <= MAX_COMPARE:
        raise HTTPException(status_code=422, detail=f"Compare 2 to {MAX_COMPARE} opportunities.")
    aspect_list = [a for a in (aspects or "").split(",") if a.strip()] or None
    return retrieval.compare_postings(item_ids, aspect_list)


@router.get("/items/{item_id}/resume-match")
def resume_match(
    item_id: int,
    limit: int = Query(6, ge=1, le=20),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    profile = ProfileRepository().get_by_user_id(db, user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="No profile found. Upload a resume first.")
    result = match_resume(profile, item_id, limit=limit)
    if result is None:
        raise HTTPException(status_code=404, detail="Opportunity not found.")
    return result


@router.post("/items/{item_id}/ask")
async def ask(item_id: int, body: AskRequest, user: User = Depends(get_current_user)) -> dict:
    try:
        provider = provider_for()
        result = await answer_question(provider, item_id, body.question)
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Opportunity not found.")
    return {
        "answer": result.answer,
        "not_found": result.not_found,
        "citations": result.citations,
        "passages": result.passages,
    }
