"""Notifications: create (idempotently) and the jobs that generate them.

* `notify_new_matches`  – new postings whose embedding is close to a user's profile (FR-5)
* `notify_deadlines`    – bookmarked postings closing within a few days
Both are safe to run repeatedly: a (user, dedupe_key) pair is only ever created once.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.activity import ItemFeedback, Notification
from app.models.bookmark import Bookmark
from app.models.profile import Profile
from app.models.rss_item import RssItem

logger = logging.getLogger("notify")

MATCH_THRESHOLD = 0.45   # cosine similarity; MiniLM scores related text around 0.3–0.6
MATCH_LOOKBACK_HOURS = 48
MAX_MATCHES_PER_USER_RUN = 5
DEADLINE_WINDOW_DAYS = 3


def create_notification(
    db: Session, *, user_id: int, kind: str, title: str, body: str = "",
    rss_item_id: int | None = None, dedupe_key: str,
) -> bool:
    """Insert unless this user already has one with the same key. True if created."""
    stmt = (
        pg_insert(Notification)
        .values(user_id=user_id, kind=kind, title=title[:300], body=body[:1000], rss_item_id=rss_item_id, dedupe_key=dedupe_key)
        .on_conflict_do_nothing(constraint="uq_notifications_user_dedupe")
    )
    created = db.execute(stmt).rowcount > 0
    db.commit()
    return created


def notify_new_matches(
    db: Session, *, threshold: float = MATCH_THRESHOLD, lookback_hours: int = MATCH_LOOKBACK_HOURS
) -> int:
    since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    created = 0
    profiles = db.query(Profile).filter(Profile.profile_embedding.isnot(None)).all()
    for profile in profiles:
        distance = RssItem.embedding.cosine_distance(list(profile.profile_embedding))
        hidden = select(ItemFeedback.rss_item_id).where(
            ItemFeedback.user_id == profile.user_id, ItemFeedback.value.in_(("hide", "down"))
        )
        rows = (
            db.query(RssItem, distance)
            .filter(RssItem.embedding.isnot(None), RssItem.created_at >= since, distance <= 1 - threshold,
                    RssItem.id.notin_(hidden), ~RssItem.flags.any("scam-risk"), RssItem.visible())
            .order_by(distance)
            .limit(MAX_MATCHES_PER_USER_RUN)
            .all()
        )
        for item, dist in rows:
            if create_notification(
                db, user_id=profile.user_id, kind="new_match",
                title=f"New match: {item.title}",
                body=f"{item.source_name} · {round((1 - float(dist)) * 100)}% match with your profile",
                rss_item_id=item.id, dedupe_key=f"match:{item.id}",
            ):
                created += 1
    return created


def notify_deadlines(db: Session, *, window_days: int = DEADLINE_WINDOW_DAYS) -> int:
    now = datetime.now(timezone.utc)
    rows = (
        db.query(Bookmark, RssItem)
        .join(RssItem, RssItem.id == Bookmark.rss_item_id)
        .filter(
            Bookmark.status.in_(("saved",)),
            RssItem.application_deadline.isnot(None),
            and_(RssItem.application_deadline >= now, RssItem.application_deadline <= now + timedelta(days=window_days)),
        )
        .all()
    )
    created = 0
    for bookmark, item in rows:
        days = max((item.application_deadline - now).days, 0)
        when = "today" if days == 0 else f"in {days} day{'s' if days != 1 else ''}"
        if create_notification(
            db, user_id=bookmark.user_id, kind="deadline",
            title=f"Closing {when}: {item.title}",
            body=f"{item.source_name} · deadline {item.application_deadline:%d %b %Y}. You saved it but have not applied.",
            rss_item_id=item.id, dedupe_key=f"deadline:{item.id}:{item.application_deadline:%Y%m%d}",
        ):
            created += 1
    return created
