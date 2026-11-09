"""Notifications: list, mark read, and a live Server-Sent Events stream.

  GET  /api/notifications?unread_only=   latest notifications + unread count
  POST /api/notifications/read           mark some (ids) or all as read
  GET  /api/notifications/stream         SSE: pushes new notifications as they are created

The stream uses SSE rather than a WebSocket on purpose: the browser talks only
to the Next.js proxy, which attaches the httpOnly session cookie and streams
SSE through untouched (a WebSocket could not carry that cookie to FastAPI).
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, update
from sqlalchemy.orm import Session

from app.db import SessionLocal, get_db
from app.middleware.auth import get_current_user
from app.models.activity import Notification
from app.models.user import User

router = APIRouter(prefix="/notifications", tags=["notifications"])

STREAM_POLL_SECONDS = 3.0
STREAM_HEARTBEAT_SECONDS = 20.0


class ReadRequest(BaseModel):
    ids: Optional[list[int]] = None  # omit to mark everything read


def _dict(n: Notification) -> dict:
    return {"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "rss_item_id": n.rss_item_id,
            "read": n.read_at is not None, "created_at": n.created_at}


@router.get("")
def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(30, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    q = db.query(Notification).filter(Notification.user_id == user.id)
    if unread_only:
        q = q.filter(Notification.read_at.is_(None))
    rows = q.order_by(Notification.id.desc()).limit(limit).all()
    unread = (
        db.query(func.count(Notification.id))
        .filter(Notification.user_id == user.id, Notification.read_at.is_(None))
        .scalar()
    )
    return {"unread": unread, "notifications": [_dict(n) for n in rows]}


@router.post("/read")
def mark_read(body: ReadRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    stmt = update(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))
    if body.ids is not None:
        stmt = stmt.where(Notification.id.in_(body.ids))
    result = db.execute(stmt.values(read_at=datetime.now(timezone.utc)))
    db.commit()
    return {"marked": result.rowcount}


def _fetch_after(user_id: int, last_id: int) -> list[dict]:
    db = SessionLocal()
    try:
        rows = (
            db.query(Notification)
            .filter(Notification.user_id == user_id, Notification.id > last_id)
            .order_by(Notification.id)
            .limit(50)
            .all()
        )
        return [_dict(n) for n in rows]
    finally:
        db.close()


def _latest_id(user_id: int) -> int:
    db = SessionLocal()
    try:
        return db.query(func.coalesce(func.max(Notification.id), 0)).filter(Notification.user_id == user_id).scalar()
    finally:
        db.close()


@router.get("/stream")
async def stream(request: Request, user: User = Depends(get_current_user)) -> StreamingResponse:
    user_id = user.id
    last_id = _latest_id(user_id)

    async def events():
        nonlocal last_id
        idle = 0.0
        yield "retry: 5000\n\n"
        while not await request.is_disconnected():
            fresh = await asyncio.to_thread(_fetch_after, user_id, last_id)
            for n in fresh:
                last_id = max(last_id, n["id"])
                yield f"event: notification\ndata: {json.dumps(n, default=str)}\n\n"
                idle = 0.0
            if idle >= STREAM_HEARTBEAT_SECONDS:
                yield ": keep-alive\n\n"
                idle = 0.0
            await asyncio.sleep(STREAM_POLL_SECONDS)
            idle += STREAM_POLL_SECONDS

    return StreamingResponse(
        events(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
