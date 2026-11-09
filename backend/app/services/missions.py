"""Missions: saved natural-language searches that report only new, verified matches.

    "remote paid ML internships, at least ₹20k/month, deadline after December"
        → category=internship, remote_only, min_stipend=20000, deadline_after=Dec 1

`parse_query` pulls structured constraints out of the sentence (the rest stays
as the semantic/keyword query); `run_mission` applies them to the posting
table and records each posting at most once per mission, so every run reports
only what is new.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.activity import ItemFeedback, Mission, MissionMatch
from app.models.rss_item import RssItem
from app.services.insights import signals
from app.services.matching.embeddings import get_embedder, query_text
from app.services.notify import create_notification

logger = logging.getLogger("missions")

_CATEGORY_WORDS = {
    "internship": r"internships?|interns?\b", "hackathon": r"hackathons?", "research": r"research|phd|fellowships?",
    "freelance": r"freelanc\w*|gigs?\b", "course": r"courses?|certifications?|moocs?", "job": r"\bjobs?\b|full[- ]time|new grad",
}
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
_STOP = {"a", "an", "the", "and", "or", "for", "in", "at", "with", "that", "are", "is", "to", "of", "me", "find", "show", "any", "new",
         "paid", "remote", "least", "month", "per", "deadline", "after", "before", "stipend"}


def parse_query(text: str, *, today: datetime | None = None) -> dict:
    today = today or datetime.now(timezone.utc)
    low = text.lower()
    category = next((c for c, pat in _CATEGORY_WORDS.items() if re.search(pat, low)), None)
    remote_only = bool(re.search(r"\bremote\b|work from home|\bwfh\b", low))

    min_stipend = None
    m = re.search(r"(?:≥|>=|at least|min(?:imum)?|above|over|>)\s*(?:of\s*)?(?:₹|rs\.?|inr|\$)?\s?(\d[\d,]*(?:\.\d+)?)\s?(k|lakhs?|l)?", low)
    if m:
        amount = float(m.group(1).replace(",", ""))
        unit = m.group(2) or ""
        amount *= 1000 if unit == "k" else 100000 if unit.startswith("l") else 1
        if amount >= 100:
            min_stipend = amount

    deadline_after = None
    m = re.search(r"deadline\s+(?:is\s+)?(?:after|beyond|from)\s+(?:the\s+)?(?:end of\s+)?([a-z]{3})[a-z]*(?:\s+(20\d\d))?", low)
    if m and m.group(1) in _MONTHS:
        month = _MONTHS[m.group(1)]
        year = int(m.group(2)) if m.group(2) else today.year + (1 if month < today.month else 0)
        deadline_after = datetime(year, month, 1, tzinfo=timezone.utc)

    words = [w for w in re.findall(r"[a-z][a-z+#.]{1,}", low) if w not in _STOP and not re.fullmatch(_CATEGORY_WORDS.get(category or "", "$^"), w)]
    return {"category": category, "remote_only": remote_only, "min_stipend": min_stipend,
            "deadline_after": deadline_after, "keywords": words[:12]}


def run_mission(db: Session, mission: Mission, *, limit: int = 10, notify: bool = True) -> list[dict]:
    """Find postings matching the mission that it has not reported before."""
    seen = db.query(MissionMatch.rss_item_id).filter(MissionMatch.mission_id == mission.id)
    dismissed = db.query(ItemFeedback.rss_item_id).filter(
        ItemFeedback.user_id == mission.user_id, ItemFeedback.value.in_(("hide", "down")))
    now = datetime.now(timezone.utc)
    q = db.query(RssItem).filter(
        RssItem.id.notin_(seen), RssItem.id.notin_(dismissed),
        ~RssItem.flags.any("scam-risk"),
        (RssItem.application_deadline.is_(None)) | (RssItem.application_deadline >= now),
    )
    if mission.category:
        q = q.filter(RssItem.category == mission.category)
    if mission.deadline_after:
        q = q.filter(RssItem.application_deadline >= mission.deadline_after)

    parsed = parse_query(mission.query)
    keywords = parsed["keywords"] or mission.query.split()
    embedder = get_embedder(load=False)
    scored: list[tuple[RssItem, float]] = []
    if embedder is not None:
        vector = embedder.embed([query_text(keywords)])[0]
        distance = RssItem.embedding.cosine_distance(vector)
        rows = q.filter(RssItem.embedding.isnot(None)).add_columns(distance).order_by(distance).limit(200).all()
        scored = [(r, 1 - float(d)) for r, d in rows if 1 - float(d) >= 0.3]
    if not scored:  # no model (or nothing close): OR-match the keywords
        tsq = func.websearch_to_tsquery("english", " OR ".join(keywords))
        vec = func.to_tsvector("english", RssItem.title + " " + func.coalesce(RssItem.summary, ""))
        rows = q.filter(vec.op("@@")(tsq)).add_columns(func.ts_rank(vec, tsq)).order_by(func.ts_rank(vec, tsq).desc()).limit(200).all()
        scored = [(r, float(s)) for r, s in rows]

    matches: list[dict] = []
    for item, score in scored:
        body = f"{item.title}\n{item.summary or ''}"
        if mission.remote_only and not signals.detect_remote(item.title, item.summary or "", item.tags or []):
            continue
        if mission.min_stipend:
            stipend = signals.extract_stipend(body)
            if not stipend or stipend["amount"] < mission.min_stipend:
                continue
        matches.append({"item": item, "score": score})
        if len(matches) >= limit:
            break

    for m in matches:
        db.execute(pg_insert(MissionMatch).values(mission_id=mission.id, rss_item_id=m["item"].id, score=m["score"])
                   .on_conflict_do_nothing())
    mission.last_run_at = now
    db.commit()

    if notify and matches:
        create_notification(
            db, user_id=mission.user_id, kind="mission",
            title=f"Mission “{mission.name}”: {len(matches)} new match{'es' if len(matches) != 1 else ''}",
            body="; ".join(m["item"].title for m in matches[:3]),
            rss_item_id=matches[0]["item"].id,
            dedupe_key=f"mission:{mission.id}:{now:%Y%m%d%H%M%S}",
        )
    return [{"id": m["item"].id, "title": m["item"].title, "url": m["item"].url,
             "category": m["item"].category, "source_name": m["item"].source_name, "score": round(m["score"], 3)}
            for m in matches]


def run_due_missions(db: Session, *, every_hours: int = 24) -> int:
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=every_hours)
    due = db.query(Mission).filter(Mission.active.is_(True), (Mission.last_run_at.is_(None)) | (Mission.last_run_at <= cutoff)).all()
    total = 0
    for mission in due:
        try:
            total += len(run_mission(db, mission))
        except Exception:
            logger.exception("Mission %s failed", mission.id)
            db.rollback()
    return total
