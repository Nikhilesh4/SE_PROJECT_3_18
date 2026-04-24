"""Bookmark API — authenticated endpoints for saving/removing opportunities.

Architecture:
  - All endpoints require JWT authentication via get_current_user dependency.
  - Bookmark is a simple toggle: POST adds if missing, removes if exists.
  - GET /bookmarks returns full NormalizedRssItem data (joined from rss_items).
  - GET /bookmarks/ids returns lightweight list of rss_item IDs for UI state.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.middleware.auth import get_current_user
from app.models.bookmark import Bookmark
from app.models.rss_item import RssItem
from app.models.user import User
from app.schemas.rss_item import NormalizedRssItem

router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])


# ── Toggle Bookmark ──────────────────────────────────────────────────────────

@router.post("/{item_id}")
def toggle_bookmark(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Toggle a bookmark on an RSS item.
    If the bookmark exists, remove it (returns action='removed').
    If it doesn't exist, add it (returns action='added').
    """
    # Verify the RSS item exists
    rss_item = db.query(RssItem).filter(RssItem.id == item_id).first()
    if not rss_item:
        raise HTTPException(status_code=404, detail="Opportunity not found.")

    existing = (
        db.query(Bookmark)
        .filter(Bookmark.user_id == user.id, Bookmark.rss_item_id == item_id)
        .first()
    )

    if existing:
        db.delete(existing)
        db.commit()
        return {"action": "removed", "rss_item_id": item_id}
    else:
        bookmark = Bookmark(user_id=user.id, rss_item_id=item_id)
        db.add(bookmark)
        db.commit()
        return {"action": "added", "rss_item_id": item_id}


# ── Remove Bookmark ──────────────────────────────────────────────────────────

@router.delete("/{item_id}")
def remove_bookmark(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Explicitly remove a bookmark. Idempotent — returns success even if not found."""
    existing = (
        db.query(Bookmark)
        .filter(Bookmark.user_id == user.id, Bookmark.rss_item_id == item_id)
        .first()
    )
    if existing:
        db.delete(existing)
        db.commit()
    return {"action": "removed", "rss_item_id": item_id}


# ── List Bookmarked Items ───────────────────────────────────────────────────

@router.get("", response_model=List[NormalizedRssItem])
def list_bookmarks(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    category: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[NormalizedRssItem]:
    """
    Return all bookmarked opportunities for the authenticated user.
    Joins bookmarks → rss_items to return full item data.
    """
    q = (
        db.query(RssItem)
        .join(Bookmark, Bookmark.rss_item_id == RssItem.id)
        .filter(Bookmark.user_id == user.id)
    )
    if category:
        q = q.filter(RssItem.category == category)
    q = q.order_by(Bookmark.created_at.desc())
    items = q.offset(offset).limit(limit).all()

    return [
        NormalizedRssItem(
            title=item.title,
            url=item.url,
            summary=item.summary or "",
            published_at=item.published_at,
            application_deadline=item.application_deadline,
            category=item.category,
            source_name=item.source_name,
            feed_url=item.feed_url,
            tags=item.tags or [],
            author=item.author,
            guid=item.guid,
        )
        for item in items
    ]


# ── List Bookmarked IDs (lightweight) ───────────────────────────────────────

@router.get("/ids")
def list_bookmark_ids(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Return just the rss_item IDs that the user has bookmarked.
    Lightweight endpoint used by the frontend to determine bookmark state
    without fetching full item data.
    """
    rows = (
        db.query(Bookmark.rss_item_id)
        .filter(Bookmark.user_id == user.id)
        .all()
    )
    return {"ids": [r[0] for r in rows]}
