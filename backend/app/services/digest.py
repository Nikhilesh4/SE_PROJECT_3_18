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

from app.models.activity import Mission, Notification
from app.models.bookmark import Bookmark
from app.models.profile import Profile
from app.models.rss_item import RssItem
from app.services import llm
from app.services.insights import explain
from app.services.notify import create_notification

logger = logging.getLogger("digest")

DIGEST_EVERY_DAYS = 7
STALE_APPLIED_DAYS = 14


MAX_ACTIONS = 3


def _action(kind: str, text: str, priority: int, item: RssItem | None = None) -> dict:
    return {"kind": kind, "text": text, "priority": priority, "item_id": item.id if item else None}


def build_actions(db: Session, user_id: int, now: datetime | None = None) -> tuple[list[dict], dict]:
    """Every action worth suggesting, best first, plus the counts they were derived from.

    All of it is computed from the user's own data (no model involved), so each suggestion can be
    traced to a row. Returned in priority order; callers take the first few.
    """
    now = now or datetime.now(timezone.utc)
    counts = dict(
        db.query(Bookmark.status, func.count()).filter(Bookmark.user_id == user_id).group_by(Bookmark.status).all()
    )
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    tracked = (
        db.query(Bookmark, RssItem).join(RssItem, RssItem.id == Bookmark.rss_item_id)
        .filter(Bookmark.user_id == user_id, Bookmark.status.in_(("saved", "applied", "interview"))).all()
    )
    closing = sorted(
        (i for b, i in tracked if b.status == "saved" and i.application_deadline and now <= i.application_deadline <= now + timedelta(days=7)),
        key=lambda i: i.application_deadline,
    )
    interviews = [i for b, i in tracked if b.status == "interview"]
    stale = sorted(
        ((b, i) for b, i in tracked if b.status == "applied" and b.updated_at and b.updated_at <= now - timedelta(days=STALE_APPLIED_DAYS)),
        key=lambda bi: bi[0].updated_at,
    )
    recent_matches = (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.kind == "new_match", Notification.created_at >= now - timedelta(days=7))
        .order_by(Notification.id.desc()).limit(3).all()
    )
    has_active_mission = db.query(Mission.id).filter(Mission.user_id == user_id, Mission.active.is_(True)).first() is not None

    acts: list[dict] = []
    if profile is None:
        acts.append(_action("profile", "Upload your resume so opportunities can be ranked for you", 1))
    for item in closing[:2]:
        acts.append(_action("deadline", f"Apply to “{item.title}” before {item.application_deadline:%d %b}", 2, item))
    for item in interviews[:1]:
        acts.append(_action("interview", f"Prepare for your interview: “{item.title}” — practise with the interview questions tool", 3, item))
    if stale:
        n = len(stale)
        acts.append(_action("follow_up", f"Follow up on {n} application{'s' if n != 1 else ''} with no update for {STALE_APPLIED_DAYS}+ days (oldest: “{stale[0][1].title}”)", 4, stale[0][1]))
    gap = _top_skill_gap(profile, [i for _, i in tracked])
    if gap:
        skill, n, total = gap
        acts.append(_action("skill_gap", f"{skill} appears in {n} of your {total} tracked roles and isn't on your profile — a small project would close the gap", 5))
    if recent_matches:
        acts.append(_action("match", f"Review your new match: {recent_matches[0].title.removeprefix('New match: ')}", 6))
    if counts.get("saved") and not counts.get("applied"):
        acts.append(_action("apply", "Apply to at least one saved opportunity this week", 6))
    if not has_active_mission and profile is not None:
        acts.append(_action("mission", "Create a mission so new matching postings reach you without searching", 7))
    if not tracked and not counts.get("offer") and not counts.get("rejected"):
        acts.append(_action("save", "Save a few opportunities from your feed to start tracking applications", 8))
    acts.sort(key=lambda a: a["priority"])
    facts = {
        "saved": counts.get("saved", 0), "applied": counts.get("applied", 0), "interview": counts.get("interview", 0),
        "offer": counts.get("offer", 0), "rejected": counts.get("rejected", 0),
        "closing_soon": [i.title for i in closing], "stale_applications": len(stale),
        "has_profile": profile is not None, "has_active_mission": has_active_mission,
    }
    return acts, facts


def _top_skill_gap(profile: Profile | None, items: list[RssItem]) -> tuple[str, int, int] | None:
    """The skill missing from the profile that the most tracked roles ask for (needs 2+ roles, or 1 of 1)."""
    if profile is None or not items:
        return None
    skills = explain.user_skills(profile)
    if not skills:
        return None
    missing: dict[str, int] = {}
    for item in items:
        for m in explain.skill_gap(item, skills)["missing"]:
            missing[m] = missing.get(m, 0) + 1
    if not missing:
        return None
    skill, n = max(sorted(missing.items()), key=lambda kv: kv[1])
    return (skill, n, len(items)) if n >= min(2, len(items)) else None


def build_digest(db: Session, user_id: int, *, polish: bool = True) -> dict:
    acts, facts = build_actions(db, user_id)
    actions = [a["text"] for a in acts[:MAX_ACTIONS]] or ["Save a few opportunities from your feed to start tracking applications"]
    facts = {**facts, "actions": actions}
    n_close = len(facts["closing_soon"])
    summary = (
        f"Tracker: {facts['saved']} saved, {facts['applied']} applied, {facts['interview']} interviewing, {facts['offer']} offers. "
        f"{n_close} deadline{'s' if n_close != 1 else ''} this week. This week: " + "; ".join(actions) + "."
    )
    polished = llm.complete_sync(
        "Rewrite the career-standup facts as a friendly 3-sentence note to a student. Use only the facts given; do not add numbers or deadlines.",
        summary,
    ) if polish else None
    return {"facts": facts, "actions": acts[:MAX_ACTIONS], "text": polished or summary}


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
