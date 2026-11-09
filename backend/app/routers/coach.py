"""Coaching, discovery tools and admin traces.

  POST /api/outreach/draft                 cold email / LinkedIn note / referral / follow-up draft (auth)
  POST /api/research/scout                 papers + suggested lab contacts (+ optional cold-email draft) (auth)
  POST /api/interview/questions            practice questions for a posting or role (auth)
  POST /api/interview/feedback             feedback on one answer (auth)
  GET  /api/insights/projects?item_id=     portfolio projects that close the skill gap (auth)
  GET  /api/insights/company?name=         indexed postings + skills in demand for a company (auth)
  GET  /api/insights/companies             companies closest to your profile (auth)
  GET  /api/memory/search?q=               search your own application notes (auth)
  POST /api/discovery/run                  run the discovery pipeline now (admin)
  GET  /api/discovery/runs                 agent run traces (admin)
"""

from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal, get_db
from app.middleware.auth import get_current_user
from app.models.activity import AgentRun
from app.models.rss_item import RssItem
from app.models.user import User
from app.repositories.profile_repository import ProfileRepository
from app.services import coach
from app.services.discovery import pipeline, scholarly
from app.services.insights import explain

router = APIRouter(tags=["coach"])


def require_admin(user: User = Depends(get_current_user)) -> User:
    admins = {e.strip().lower() for e in settings.ADMIN_EMAILS.split(",") if e.strip()}
    if user.email.lower() not in admins:
        raise HTTPException(status_code=403, detail="Admin only. Set ADMIN_EMAILS to enable.")
    return user


def _item_or_404(db: Session, item_id: int) -> RssItem:
    item = db.get(RssItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Opportunity not found.")
    return item


class OutreachBody(BaseModel):
    kind: str = Field(pattern="^(cold_email|linkedin_note|referral_request|follow_up)$")
    item_id: Optional[int] = None
    recipient: str = Field("", max_length=100)
    note: str = Field("", max_length=300)


@router.post("/outreach/draft")
async def outreach(body: OutreachBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    item = _item_or_404(db, body.item_id) if body.item_id else None
    profile = ProfileRepository().get_by_user_id(db, user.id)
    return await asyncio.to_thread(coach.draft_outreach, body.kind, student=user.name or "a student", profile=profile, item=item, recipient=body.recipient, note=body.note)


class ScoutBody(BaseModel):
    topic: str = Field(min_length=3, max_length=120)
    draft_for: Optional[str] = Field(None, max_length=100, description="Name of a returned contact to draft a cold email for")


@router.post("/research/scout")
async def research_scout(body: ScoutBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    result = await asyncio.to_thread(scholarly.scout, body.topic)
    if body.draft_for:
        contact = next((c for c in result["contacts"] if c["name"] == body.draft_for), None)
        if contact is None:
            raise HTTPException(status_code=404, detail="That contact was not in the scout results.")
        profile = ProfileRepository().get_by_user_id(db, user.id)
        result["draft"] = scholarly.template_cold_email(
            student_name=user.name or "a student", topic=body.topic, person=contact["name"],
            paper=(contact["papers"] or ["your recent work"])[0], skills=explain.user_skills(profile))
        result["draft"]["review_note"] = "This is a draft. Check every claim, add personal details, and send it yourself."
    return result


class InterviewQ(BaseModel):
    item_id: Optional[int] = None
    role: str = Field("", max_length=150)
    count: int = Field(6, ge=1, le=10)


@router.post("/interview/questions")
async def interview_q(body: InterviewQ, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    if not body.item_id and not body.role.strip():
        raise HTTPException(status_code=422, detail="Provide item_id or role.")
    item = _item_or_404(db, body.item_id) if body.item_id else None
    skills = explain.user_skills(ProfileRepository().get_by_user_id(db, user.id))
    role, summary = (item.title, item.summary or "") if item else (body.role.strip(), "")
    return await asyncio.to_thread(coach.interview_questions, role, skills, summary=summary, n=body.count)


class InterviewA(BaseModel):
    question: str = Field(min_length=3, max_length=400)
    answer: str = Field(min_length=1, max_length=4000)


@router.post("/interview/feedback")
async def interview_a(body: InterviewA, user: User = Depends(get_current_user)) -> dict:
    return await asyncio.to_thread(coach.interview_feedback, body.question, body.answer)


@router.get("/insights/projects")
def projects(item_id: int = Query(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    item = _item_or_404(db, item_id)
    gap = explain.skill_gap(item, explain.user_skills(ProfileRepository().get_by_user_id(db, user.id)))
    return {"item_id": item_id, "missing": gap["missing"], "projects": coach.project_ideas(gap["missing"], role=item.title)}


@router.get("/insights/company")
def company(name: str = Query(..., min_length=2, max_length=80), user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return coach.company_brief(db, name, profile=ProfileRepository().get_by_user_id(db, user.id))


@router.get("/insights/companies")
def companies(limit: int = Query(10, ge=1, le=30), user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    profile = ProfileRepository().get_by_user_id(db, user.id)
    return {"companies": coach.reverse_search(db, profile, limit=limit) if profile else []}


@router.get("/memory/search")
def memory(q: str = Query(..., min_length=2, max_length=200), user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return {"results": coach.search_notes(db, user.id, q)}


# ── Admin ────────────────────────────────────────────────────────────────────

class RunBody(BaseModel):
    sources: Optional[list[str]] = None
    force: bool = True


@router.post("/discovery/run")
async def discovery_run(body: RunBody, _: User = Depends(require_admin)) -> dict:
    def work() -> dict:
        db = SessionLocal()
        try:
            return pipeline.run_discovery(db, pipeline.default_adapters(), only=body.sources, force=body.force)
        finally:
            db.close()
    return await asyncio.to_thread(work)


@router.get("/discovery/runs")
def discovery_runs(limit: int = Query(20, ge=1, le=100), _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    rows = db.query(AgentRun).filter(AgentRun.kind == "discovery").order_by(AgentRun.id.desc()).limit(limit).all()
    return {"runs": [{"id": r.id, "status": r.status, "started_at": r.started_at, "finished_at": r.finished_at, "output": r.output, "steps": r.steps} for r in rows]}


# ── Source Scout (admin) ─────────────────────────────────────────────────────

class ScoutSite(BaseModel):
    url: str = Field(min_length=8, max_length=300)


class Approve(BaseModel):
    category: Optional[str] = Field(None, pattern="^(internship|hackathon|research|job|freelance|course)$")
    source_name: Optional[str] = Field(None, max_length=80)


@router.post("/discovery/source-scout")
async def source_scout_run(body: ScoutSite, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    from app.services.discovery import fetcher, source_scout
    try:
        found = await asyncio.to_thread(source_scout.scout_site, body.url)
    except fetcher.FetchBlocked as exc:
        raise HTTPException(status_code=400, detail=f"Refused: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Could not read that site ({exc.__class__.__name__}).") from exc
    run = AgentRun(kind="source_proposal", status="proposed", input={"site": body.url}, output={"proposals": [p.as_dict() for p in found]})
    db.add(run)
    db.commit()
    return {"id": run.id, "proposals": run.output["proposals"]}


@router.get("/discovery/source-proposals")
def source_proposals(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    rows = db.query(AgentRun).filter(AgentRun.kind == "source_proposal").order_by(AgentRun.id.desc()).limit(30).all()
    return {"proposals": [{"id": r.id, "status": r.status, "site": r.input.get("site"), "feeds": r.output.get("proposals", [])} for r in rows]}


@router.post("/discovery/source-proposals/{run_id}/approve")
def source_approve(run_id: int, feed_index: int = Query(0, ge=0), body: Approve | None = None, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    from app.services.discovery import source_scout
    run = db.get(AgentRun, run_id)
    if run is None or run.kind != "source_proposal":
        raise HTTPException(status_code=404, detail="Proposal not found.")
    feeds = run.output.get("proposals", [])
    if feed_index >= len(feeds):
        raise HTTPException(status_code=404, detail="No such feed in this proposal.")
    feed = feeds[feed_index]
    body = body or Approve()
    source_scout.approve(feed["url"], body.category or feed["suggested_category"], body.source_name or feed["title"])
    run.status = "approved"
    db.commit()
    return {"approved": feed["url"], "note": "Takes effect when the API/worker next restarts."}


@router.post("/discovery/source-proposals/{run_id}/reject")
def source_reject(run_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    run = db.get(AgentRun, run_id)
    if run is None or run.kind != "source_proposal":
        raise HTTPException(status_code=404, detail="Proposal not found.")
    run.status = "rejected"
    db.commit()
    return {"rejected": run_id}
