"""Application tracker (Kanban) and deadline tools, built on bookmarks.

  GET   /api/applications                 board: bookmarks grouped by status
  PATCH /api/applications/{item_id}       move a card / edit notes
  GET   /api/deadlines?days=14            saved postings closing soon
  GET   /api/bookmarks/calendar.ics       all saved deadlines as a calendar file
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.middleware.auth import get_current_user
from app.models.bookmark import APPLICATION_STATUSES, Bookmark
from app.models.rss_item import RssItem
from app.models.user import User
from app.services.insights.ics import build_ics
from app.services.rss.cache_service import RssCacheService

router = APIRouter(tags=["applications"])


class ApplicationUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=5000)


def _card(bookmark: Bookmark, item: RssItem) -> dict:
    return {
        "item": RssCacheService._row_to_schema(item).model_dump(mode="json"),
        "status": bookmark.status,
        "notes": bookmark.notes or "",
        "applied_at": bookmark.applied_at,
        "saved_at": bookmark.created_at,
        "updated_at": bookmark.updated_at,
    }


@router.get("/applications")
def board(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    rows = (
        db.query(Bookmark, RssItem)
        .join(RssItem, RssItem.id == Bookmark.rss_item_id)
        .filter(Bookmark.user_id == user.id)
        .order_by(Bookmark.updated_at.desc())
        .all()
    )
    columns: dict[str, list[dict]] = {s: [] for s in APPLICATION_STATUSES}
    for bookmark, item in rows:
        columns.setdefault(bookmark.status, []).append(_card(bookmark, item))
    return {"statuses": list(APPLICATION_STATUSES), "columns": columns, "total": len(rows)}


@router.patch("/applications/{item_id}")
def update_application(
    item_id: int,
    body: ApplicationUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    bookmark = db.get(Bookmark, (user.id, item_id))
    if bookmark is None:
        raise HTTPException(status_code=404, detail="Save this posting before tracking it.")
    if body.status is not None:
        if body.status not in APPLICATION_STATUSES:
            raise HTTPException(status_code=422, detail=f"status must be one of {', '.join(APPLICATION_STATUSES)}")
        if body.status != "saved" and bookmark.applied_at is None:
            bookmark.applied_at = datetime.now(timezone.utc)
        if body.status == "saved":
            bookmark.applied_at = None
        bookmark.status = body.status
    if body.notes is not None:
        bookmark.notes = body.notes.strip() or None
    db.commit()
    db.refresh(bookmark)
    return _card(bookmark, db.get(RssItem, item_id))


@router.get("/deadlines")
def deadlines(
    days: int = Query(14, ge=1, le=365),
    scope: str = Query("saved", pattern="^(saved|all)$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    now = datetime.now(timezone.utc)
    q = db.query(RssItem).filter(
        RssItem.application_deadline.isnot(None),
        RssItem.application_deadline >= now,
        RssItem.application_deadline <= now + timedelta(days=days),
    )
    if scope != "saved":
        q = q.filter(RssItem.visible())  # a user's own saved items stay visible
    if scope == "saved":
        q = q.join(Bookmark, Bookmark.rss_item_id == RssItem.id).filter(
            Bookmark.user_id == user.id, Bookmark.status == "saved"
        )
    items = q.order_by(RssItem.application_deadline).limit(100).all()
    return {
        "days": days,
        "scope": scope,
        "items": [
            {**RssCacheService._row_to_schema(i).model_dump(mode="json"),
             "days_left": max((i.application_deadline - now).days, 0)}
            for i in items
        ],
    }


@router.get("/bookmarks/calendar.ics")
def calendar_export(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    items = (
        db.query(RssItem)
        .join(Bookmark, Bookmark.rss_item_id == RssItem.id)
        .filter(Bookmark.user_id == user.id, RssItem.application_deadline.isnot(None))
        .order_by(RssItem.application_deadline)
        .all()
    )
    return Response(
        build_ics(items),
        media_type="text/calendar",
        headers={"Content-Disposition": 'attachment; filename="unicompass-deadlines.ics"'},
    )
