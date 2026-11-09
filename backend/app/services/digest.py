"""Weekly "career standup": one notification summarising where the user stands.

Rule-based by default (so it works with no API key); when an LLM is configured
it rewrites the facts into a short, friendly note. The facts never come from
the model: counts, titles and deadlines are computed here.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.activity import Notification
from app.models.bookmark import Bookmark
from app.models.profile import Profile
from app.models.rss_item import RssItem
from app.services import llm
from app.services.notify import create_notification

logger = logging.getLogger("digest")

DIGEST_EVERY_DAYS = 7


def build_digest(db: Session, user_id: int) -> dict:
    now = datetime.now(timezone.utc)
    counts = dict(
        db.query(Bookmark.status, func.count()).filter(Bookmark.user_id == user_id).group_by(Bookmark.status).all()
    )
    closing = (
        db.query(RssItem)
        .join(Bookmark, Bookmark.rss_item_id == RssItem.id)
        .filter(Bookmark.user_id == user_id, Bookmark.status == "saved", RssItem.application_deadline >= now,
                RssItem.application_deadline <= now + timedelta(days=7))
        .order_by(RssItem.application_deadline).limit(5).all()
    )
    recent_matches = (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.kind == "new_match", Notification.created_at >= now - timedelta(days=7))
        .order_by(Notification.id.desc()).limit(3).all()
    )
    stale = (
        db.query(Bookmark).filter(Bookmark.user_id == user_id, Bookmark.status == "applied", Bookmark.updated_at <= now - timedelta(days=14)).count()
    )

    actions: list[str] = []
    for item in closing[:2]:
        actions.append(f"Apply to “{item.title}” before {item.application_deadline:%d %b}")
    if stale:
        actions.append(f"Follow up on {stale} application{'s' if stale != 1 else ''} with no update for 2+ weeks")
    if recent_matches and len(actions) < 3:
        actions.append(f"Review your new match: {recent_matches[0].title.removeprefix('New match: ')}")
    if not counts.get("applied") and len(actions) < 3:
        actions.append("Apply to at least one saved opportunity this week")
    actions = actions[:3] or ["Save a few opportunities from your feed to start tracking applications"]

    facts = {
        "saved": counts.get("saved", 0), "applied": counts.get("applied", 0), "interview": counts.get("interview", 0),
        "offer": counts.get("offer", 0), "closing_soon": [i.title for i in closing], "actions": actions,
    }
    summary = (
        f"Tracker: {facts['saved']} saved, {facts['applied']} applied, {facts['interview']} interviewing, {facts['offer']} offers. "
        f"{len(closing)} deadline{'s' if len(closing) != 1 else ''} this week. This week: " + "; ".join(actions) + "."
    )
    polished = llm.complete_sync(
        "Rewrite the career-standup facts as a friendly 3-sentence note to a student. Use only the facts given; do not add numbers or deadlines.",
        summary,
    )
    return {"facts": facts, "text": polished or summary}


def send_due_digests(db: Session) -> int:
    """One digest per user per ISO week, only for users who have a profile or any tracked item."""
    now = datetime.now(timezone.utc)
    week = f"{now.isocalendar().year}-W{now.isocalendar().week:02d}"
    user_ids = {r[0] for r in db.query(Profile.user_id).all()} | {r[0] for r in db.query(Bookmark.user_id).distinct().all()}
    sent = 0
    for uid in user_ids:
        digest = build_digest(db, uid)
        if create_notification(db, user_id=uid, kind="digest", title="Your weekly career standup", body=digest["text"], dedupe_key=f"digest:{week}"):
            sent += 1
    return sent
