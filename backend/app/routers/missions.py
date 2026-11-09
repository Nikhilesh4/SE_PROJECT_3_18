"""Missions API: saved natural-language searches that report only new matches.

  GET    /api/missions
  POST   /api/missions            {"name", "query", "category"?}  – constraints are parsed from the sentence
  PATCH  /api/missions/{id}       {"active"?, "name"?}
  DELETE /api/missions/{id}
  POST   /api/missions/{id}/run   run now, return the new matches
  GET    /api/missions/{id}/matches
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.middleware.auth import get_current_user
from app.models.activity import Mission, MissionMatch
from app.models.rss_item import RssItem
from app.models.user import User
from app.services import missions as svc

router = APIRouter(prefix="/missions", tags=["missions"])
MAX_MISSIONS_PER_USER = 10


class MissionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    query: str = Field(min_length=3, max_length=500)
    category: Optional[str] = None


class MissionPatch(BaseModel):
    active: Optional[bool] = None
    name: Optional[str] = Field(None, min_length=1, max_length=80)


def _dict(m: Mission) -> dict:
    return {"id": m.id, "name": m.name, "query": m.query, "category": m.category, "remote_only": m.remote_only,
            "min_stipend": m.min_stipend, "deadline_after": m.deadline_after, "active": m.active,
            "last_run_at": m.last_run_at, "created_at": m.created_at}


def _own(db: Session, user: User, mission_id: int) -> Mission:
    mission = db.query(Mission).filter(Mission.id == mission_id, Mission.user_id == user.id).first()
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found.")
    return mission


@router.get("")
def list_missions(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    rows = db.query(Mission).filter(Mission.user_id == user.id).order_by(Mission.id.desc()).all()
    return {"missions": [_dict(m) for m in rows]}


@router.post("", status_code=201)
def create_mission(body: MissionCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    if db.query(Mission).filter(Mission.user_id == user.id).count() >= MAX_MISSIONS_PER_USER:
        raise HTTPException(status_code=409, detail=f"At most {MAX_MISSIONS_PER_USER} missions per user.")
    parsed = svc.parse_query(body.query)
    mission = Mission(
        user_id=user.id, name=body.name.strip(), query=body.query.strip(),
        category=body.category or parsed["category"], remote_only=parsed["remote_only"],
        min_stipend=parsed["min_stipend"], deadline_after=parsed["deadline_after"],
    )
    db.add(mission)
    db.commit()
    db.refresh(mission)
    return _dict(mission)


@router.patch("/{mission_id}")
def patch_mission(mission_id: int, body: MissionPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    mission = _own(db, user, mission_id)
    if body.active is not None:
        mission.active = body.active
    if body.name is not None:
        mission.name = body.name.strip()
    db.commit()
    return _dict(mission)


@router.delete("/{mission_id}")
def delete_mission(mission_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    db.delete(_own(db, user, mission_id))
    db.commit()
    return {"deleted": mission_id}


@router.post("/{mission_id}/run")
def run_now(mission_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    mission = _own(db, user, mission_id)
    return {"new_matches": svc.run_mission(db, mission)}


@router.get("/{mission_id}/matches")
def matches(mission_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    _own(db, user, mission_id)
    rows = (
        db.query(RssItem, MissionMatch.score, MissionMatch.created_at)
        .join(MissionMatch, MissionMatch.rss_item_id == RssItem.id)
        .filter(MissionMatch.mission_id == mission_id)
        .order_by(MissionMatch.created_at.desc()).limit(100).all()
    )
    return {"matches": [{"id": i.id, "title": i.title, "url": i.url, "category": i.category,
                         "source_name": i.source_name, "score": s, "found_at": at} for i, s, at in rows]}
