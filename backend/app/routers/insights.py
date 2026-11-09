"""Search, per-posting insights, ranking feedback and market trends.

  GET    /api/search                     full-text search + facets (category, source, remote, stipend, deadline)
  GET    /api/insights/items/{id}        why it ranks, skill gap, scam / eligibility / stipend signals (auth)
  GET    /api/insights/trends            skill demand and stipend stats across recent postings
  POST   /api/feedback/{id}              {"value": "up" | "down" | "hide"} (auth)
  DELETE /api/feedback/{id}              undo (auth)
  GET    /api/feedback                   the user's feedback (auth)
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db import get_db
from app.middleware.auth import get_current_user, get_optional_user
from app.models.activity import ItemFeedback
from app.models.rss_item import RssItem
from app.models.user import User
from app.repositories.profile_repository import ProfileRepository
from app.services.insights import explain, signals
from app.services.rss.cache_service import RssCacheService

router = APIRouter(tags=["insights"])

FEEDBACK_VALUES = ("up", "down", "hide")


def with_signals(item: RssItem) -> dict:
    """Item as a dict plus cheap derived fields shown on cards."""
    text_ = f"{item.title}\n{item.summary or ''}"
    stipend = signals.extract_stipend(text_)
    scam = signals.assess_scam_risk(item.title, item.summary or "", item.url)
    data = RssCacheService._row_to_schema(item).model_dump(mode="json")
    data["remote"] = signals.detect_remote(item.title, item.summary or "", item.tags or [])
    data["stipend_inr_month"] = stipend["amount"] if stipend else None
    data["scam_risk"] = scam.score if scam.score else 0
    if scam.risky and "scam-risk" not in data["flags"]:
        data["flags"] = [*data["flags"], "scam-risk"]
    return data


# ── Search ───────────────────────────────────────────────────────────────────

@router.get("/search")
def search(
    q: Optional[str] = Query(None, max_length=200, description="Words to match; websearch syntax (quotes, -exclude, OR)"),
    category: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    remote: Optional[bool] = Query(None),
    min_stipend: Optional[float] = Query(None, ge=0, description="INR per month"),
    closing_within_days: Optional[int] = Query(None, ge=1, le=365),
    active_only: bool = Query(True),
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> dict:
    now = datetime.now(timezone.utc)
    query = db.query(RssItem).filter(RssItem.visible())
    if category:
        query = query.filter(RssItem.category == category)
    if source:
        query = query.filter(RssItem.source_name == source)
    if active_only:
        query = query.filter(
            (RssItem.application_deadline >= now)
            | (RssItem.application_deadline.is_(None) & (func.coalesce(RssItem.published_at, RssItem.created_at) >= now - timedelta(days=45)))
        )
    if closing_within_days:
        query = query.filter(RssItem.application_deadline.isnot(None), RssItem.application_deadline >= now,
                             RssItem.application_deadline <= now + timedelta(days=closing_within_days))
    if user is not None:
        hidden = db.query(ItemFeedback.rss_item_id).filter(
            ItemFeedback.user_id == user.id, ItemFeedback.value.in_(("hide", "down")))
        query = query.filter(RssItem.id.notin_(hidden))

    if q and q.strip():
        vector = func.to_tsvector("english", RssItem.title + " " + func.coalesce(RssItem.summary, "") + " " + func.array_to_string(RssItem.tags, " "))
        tsq = func.websearch_to_tsquery("english", q)
        rank = func.ts_rank(vector, tsq)
        rows = query.filter(vector.op("@@")(tsq)).order_by(rank.desc(), RssItem.published_at.desc().nullslast()).limit(500).all()
    else:
        rows = query.order_by(RssItem.published_at.desc().nullslast(), RssItem.created_at.desc()).limit(500).all()

    results = [with_signals(r) for r in rows]
    if remote is not None:
        results = [r for r in results if r["remote"] == remote]
    if min_stipend is not None:
        results = [r for r in results if (r["stipend_inr_month"] or 0) >= min_stipend]

    facets = {
        "categories": dict(Counter(r["category"] for r in results)),
        "sources": dict(Counter(r["source_name"] for r in results).most_common(15)),
        "remote": sum(1 for r in results if r["remote"]),
    }
    return {"total": len(results), "facets": facets, "items": results[offset: offset + limit]}


# ── Per-posting insights ─────────────────────────────────────────────────────

@router.get("/insights/items/{item_id}")
def item_insights(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    item = db.get(RssItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Opportunity not found.")
    profile = ProfileRepository().get_by_user_id(db, user.id)
    body = f"{item.title}\n{item.summary or ''}"
    scam = signals.assess_scam_risk(item.title, item.summary or "", item.url)
    rules = signals.parse_eligibility(body)
    return {
        "item_id": item.id,
        "has_profile": profile is not None,
        "ranking": explain.explain_ranking(db, item, profile),
        "skill_gap": explain.skill_gap(item, explain.user_skills(profile)),
        "stipend": signals.extract_stipend(body),
        "remote": signals.detect_remote(item.title, item.summary or "", item.tags or []),
        "scam": {"score": scam.score, "risky": scam.risky, "reasons": scam.reasons},
        "eligibility": {
            "years": rules.years, "min_cgpa": rules.min_cgpa, "branches": rules.branches, "notes": rules.notes,
        },
        "provenance": {"discovered_by": item.discovered_by, "confidence": item.confidence,
                       "verified_at": item.verified_at, "flags": list(item.flags or [])},
    }


@router.get("/insights/trends")
def trends(
    days: int = Query(30, ge=1, le=180),
    limit: int = Query(15, ge=1, le=50),
    db: Session = Depends(get_db),
) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.query(RssItem).filter(RssItem.visible(), func.coalesce(RssItem.published_at, RssItem.created_at) >= since).limit(5000).all()
    skill_counts: Counter[str] = Counter()
    by_category: Counter[str] = Counter()
    stipends: dict[str, list[float]] = {}
    for r in rows:
        by_category[r.category] += 1
        skill_counts.update(set(signals.extract_skills(f"{r.title}\n{r.summary or ''}\n{' '.join(r.tags or [])}")))
        s = signals.extract_stipend(f"{r.title}\n{r.summary or ''}")
        if s:
            stipends.setdefault(r.category, []).append(s["amount"])
    return {
        "days": days,
        "postings": len(rows),
        "by_category": dict(by_category),
        "top_skills": [{"skill": k, "postings": v} for k, v in skill_counts.most_common(limit)],
        "stipend_inr_month": {
            c: {"count": len(v), "median": round(median(v)), "min": round(min(v)), "max": round(max(v))}
            for c, v in stipends.items()
        },
    }


# ── Feedback ─────────────────────────────────────────────────────────────────

class FeedbackBody(BaseModel):
    value: str


@router.post("/feedback/{item_id}")
def set_feedback(item_id: int, body: FeedbackBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    if body.value not in FEEDBACK_VALUES:
        raise HTTPException(status_code=422, detail=f"value must be one of {', '.join(FEEDBACK_VALUES)}")
    if db.get(RssItem, item_id) is None:
        raise HTTPException(status_code=404, detail="Opportunity not found.")
    stmt = pg_insert(ItemFeedback).values(user_id=user.id, rss_item_id=item_id, value=body.value)
    db.execute(stmt.on_conflict_do_update(index_elements=["user_id", "rss_item_id"], set_={"value": body.value}))
    db.commit()
    return {"rss_item_id": item_id, "value": body.value}


@router.delete("/feedback/{item_id}")
def clear_feedback(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    db.query(ItemFeedback).filter(ItemFeedback.user_id == user.id, ItemFeedback.rss_item_id == item_id).delete()
    db.commit()
    return {"rss_item_id": item_id, "value": None}


@router.get("/feedback")
def list_feedback(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    rows = db.query(ItemFeedback).filter(ItemFeedback.user_id == user.id).all()
    return {"feedback": {r.rss_item_id: r.value for r in rows}}
