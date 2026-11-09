"""The multi-agent discovery pipeline.

    Planner ─► source workers ─► Extractor ─► Verifier ─► Enricher ─► persist (+ embed/RAG via the workers)

Each stage is a plain function so it can be tested and traced on its own. Every
run writes an `agent_runs` row with one step per stage (counts, timings, what
was dropped and why), so you can always answer "why did this show up / not show up".

Guardrails (enforced here and in `fetcher`):
* a per-run budget: max pages the Enricher may fetch, max LLM-assisted extractions
* domain allowlist and SSRF/robots protection on every fetch
* fetched text is data: it is stored and summarised, never executed or obeyed
* agents only add postings to the catalogue; they never apply, email or message anyone
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy.orm import Session

from app.config import settings
from app.models.activity import AgentRun
from app.models.rss_item import RssItem
from app.repositories.rss_repository import RssItemRepository
from app.schemas.rss_item import NormalizedRssItem
from app.services.adapters.base_adapter import OpportunityAdapter
from app.services.discovery import fetcher
from app.services.discovery.textutil import html_to_text
from app.services.insights import signals
from app.services.rss.filter import is_opportunity_post

logger = logging.getLogger("discovery.pipeline")

ENRICH_MAX_PAGES = 25
ENRICH_SUMMARY_CHARS = 2000
VERIFY_MAX_LINK_CHECKS = 60


# ── Trace ────────────────────────────────────────────────────────────────────

class Trace:
    """Collects per-stage steps and persists them as an agent_runs row."""

    def __init__(self, db: Session, kind: str, user_id: int | None = None, input: dict | None = None) -> None:
        self.db = db
        self.run = AgentRun(kind=kind, user_id=user_id, input=input or {}, steps=[])
        db.add(self.run)
        db.commit()
        self._steps: list[dict] = []

    def step(self, name: str, **data) -> None:
        self._steps.append({"stage": name, "at": datetime.now(timezone.utc).isoformat(), **data})
        logger.info("[%s #%s] %s %s", self.run.kind, self.run.id, name, data)

    def finish(self, status: str = "ok", output: dict | None = None) -> None:
        self.run.status, self.run.output, self.run.steps = status, output or {}, list(self._steps)
        self.run.finished_at = datetime.now(timezone.utc)
        self.db.commit()


# ── Planner ──────────────────────────────────────────────────────────────────

@dataclass
class Plan:
    sources: list[str] = field(default_factory=list)
    reasons: dict[str, str] = field(default_factory=dict)


def plan_sources(available: dict[str, OpportunityAdapter], *, last_run_age_hours: dict[str, float] | None = None, min_interval_hours: dict[str, float] | None = None) -> Plan:
    """Pick which source workers run now: skip ones that ran too recently (HN posts monthly, ATS daily …)."""
    ages = last_run_age_hours or {}
    mins = min_interval_hours or {}
    plan = Plan()
    for name in available:
        need = mins.get(name, 6)
        age = ages.get(name)
        if age is not None and age < need:
            plan.reasons[name] = f"skipped: ran {age:.1f}h ago (< {need}h)"
            continue
        plan.sources.append(name)
        plan.reasons[name] = "due"
    return plan


# ── Verifier ─────────────────────────────────────────────────────────────────

@dataclass
class Verdict:
    keep: bool
    confidence: float
    flags: list[str] = field(default_factory=list)
    reason: str = ""


def verify(item: NormalizedRssItem, *, link_checker: Callable[[str], bool | None] | None = None, now: datetime | None = None) -> Verdict:
    """Is this a live, legitimate, current opening? Link alive · deadline future · scam signals · category sanity."""
    now = now or datetime.now(timezone.utc)
    flags = list(item.flags)
    confidence = item.confidence if item.confidence is not None else 0.6

    if item.application_deadline is not None:
        dl = item.application_deadline if item.application_deadline.tzinfo else item.application_deadline.replace(tzinfo=timezone.utc)
        if dl < now:
            return Verdict(False, 0.0, flags, "deadline already passed")

    scam = signals.assess_scam_risk(item.title, item.summary, item.url)
    if scam.risky:
        flags.append("scam-risk")
        confidence = min(confidence, 0.2)
        if scam.score >= 80:
            return Verdict(False, confidence, flags, f"scam signals: {', '.join(scam.reasons)}")

    if item.discovered_by in ("web_search", "hn_whoishiring") and not is_opportunity_post(item.title, item.summary, item.category):
        return Verdict(False, 0.0, flags, "does not look like an opportunity")

    if link_checker is not None and item.url.startswith("http"):
        alive = link_checker(item.url)
        if alive is False:
            return Verdict(False, 0.0, flags, "link is dead (404/unreachable)")
        if alive is True:
            confidence = min(1.0, confidence + 0.05)
        else:
            flags.append("link-unchecked")
    return Verdict(True, round(confidence, 2), sorted(set(flags)), "ok")


def dedupe(items: list[NormalizedRssItem]) -> tuple[list[NormalizedRssItem], int]:
    """Drop the same role seen via different channels: same URL, or same normalised title + company.

    The higher-confidence copy wins and keeps its original position.
    """
    kept: list[NormalizedRssItem | None] = []
    index: dict[str, int] = {}
    dropped = 0
    for it in items:
        title_key = "t:" + re.sub(r"[^a-z0-9]+", " ", f"{it.title} {it.author or ''}".lower()).strip()
        keys = [f"u:{it.url}", title_key]
        pos = next((index[k] for k in keys if k in index), None)
        if pos is None:
            pos = len(kept)
            kept.append(it)
        else:
            dropped += 1
            if (it.confidence or 0) > (kept[pos].confidence or 0):
                kept[pos] = it
        for k in keys:
            index[k] = pos
    return [i for i in kept if i is not None], dropped


# ── Enricher ─────────────────────────────────────────────────────────────────

def enrich(db: Session, *, limit: int = ENRICH_MAX_PAGES, fetch: Callable[[str], str | None] | None = None) -> int:
    """Fetch the full posting page for thin summaries so Q&A, stipend and skills have real text.

    Only rows from agent channels or with very short summaries are touched, each at most once.
    Re-embedding and RAG re-indexing happen automatically: changing the summary resets the vector.
    """
    def default_fetch(url: str) -> str | None:
        try:
            page = fetcher.fetch_page(url)
        except fetcher.FetchBlocked:
            return None
        except Exception:
            return None
        return None if page.status >= 400 else page.text

    fetch = fetch or default_fetch
    rows = (
        db.query(RssItem)
        .filter(RssItem.enriched_at.is_(None), RssItem.url.like("http%"), RssItem.discovered_by.notin_(["hn_whoishiring", "programs"]))
        .filter((RssItem.discovered_by != "rss") | (func_length(RssItem.summary) < 400))
        .order_by(RssItem.id.desc()).limit(limit).all()
    )
    done = 0
    for row in rows:
        row.enriched_at = datetime.now(timezone.utc)  # mark even on failure: never retry forever
        raw = fetch(row.url)
        if raw:
            text = html_to_text(raw, max_chars=ENRICH_SUMMARY_CHARS)
            if len(text) > len(row.summary or "") + 100:
                row.summary = text
                done += 1
    db.commit()
    return done


def func_length(col):
    from sqlalchemy import func
    return func.length(func.coalesce(col, ""))


# ── Ingestion QA ─────────────────────────────────────────────────────────────

def ingestion_qa(db: Session, *, limit: int = 500) -> dict:
    """Flag stored postings that the regex content filter lets through but are really blog posts/news.

    Flagged rows get `not-opportunity` and drop out of the feed (they are not deleted, so a
    mistaken flag can be reversed). Postings from structured sources (ATS/Devpost/programs) are trusted.
    """
    from sqlalchemy import func
    rows = (
        db.query(RssItem)
        .filter(RssItem.discovered_by == "rss", ~RssItem.flags.any("not-opportunity"), ~RssItem.flags.any("qa-checked"))
        .order_by(RssItem.id.desc()).limit(limit).all()
    )
    flagged = 0
    for row in rows:
        row.flags = [*(row.flags or []), "qa-checked"]
        if not is_opportunity_post(row.title, row.summary or "", row.category) or _looks_like_article(row):
            row.flags = [*row.flags, "not-opportunity"]
            flagged += 1
    db.commit()
    return {"checked": len(rows), "flagged": flagged}


_ARTICLE_TITLE = re.compile(r"^(how to|why |what is|what are|top \d+|\d+ (ways|tips|reasons)|the (best|ultimate) guide|guide to|opinion:|report:|announces?|raises \$)", re.I)


def _looks_like_article(row: RssItem) -> bool:
    return bool(_ARTICLE_TITLE.search(row.title.strip()))


# ── Orchestration ────────────────────────────────────────────────────────────

def run_discovery(db: Session, adapters: dict[str, OpportunityAdapter], *, link_checker=None, enrich_fetch=None, only: list[str] | None = None, force: bool = False) -> dict:
    """One full pipeline run over the given source workers. Returns a summary (also stored in agent_runs)."""
    trace = Trace(db, "discovery", input={"sources": list(adapters)})
    try:
        ages = {}
        if not force:
            for name in adapters:
                last = db.query(AgentRun).filter(AgentRun.kind == "discovery_source", AgentRun.status == "ok", AgentRun.input["source"].astext == name).order_by(AgentRun.id.desc()).first()
                if last and last.finished_at:
                    ages[name] = (datetime.now(timezone.utc) - last.finished_at).total_seconds() / 3600
        plan = plan_sources({n: a for n, a in adapters.items() if not only or n in only}, last_run_age_hours=ages,
                            min_interval_hours={"hn": 24, "ats": 6, "devpost": 12, "programs": 168})
        trace.step("plan", sources=plan.sources, reasons=plan.reasons)

        gathered: list[NormalizedRssItem] = []
        for name in plan.sources:
            t0 = time.monotonic()
            try:
                found = adapters[name].fetch_opportunities()
                status = "ok"
            except Exception as exc:
                found, status = [], "error"
                trace.step("source_error", source=name, error=str(exc)[:200])
            gathered.extend(found)
            trace.step("source", source=name, found=len(found), seconds=round(time.monotonic() - t0, 2))
            src_run = AgentRun(kind="discovery_source", status=status, input={"source": name}, output={"found": len(found)}, finished_at=datetime.now(timezone.utc))
            db.add(src_run); db.commit()

        items, dup = dedupe(gathered)
        trace.step("extract", valid=len(items), duplicates_dropped=dup)

        kept, dropped = [], {}
        checks = 0
        for it in items:
            checker = link_checker if (link_checker and checks < VERIFY_MAX_LINK_CHECKS and it.discovered_by in ("web_search", "hn_whoishiring")) else None
            if checker:
                checks += 1
            v = verify(it, link_checker=checker)
            if not v.keep:
                dropped[v.reason] = dropped.get(v.reason, 0) + 1
                continue
            it.confidence, it.flags = v.confidence, v.flags
            kept.append(it)
        trace.step("verify", kept=len(kept), dropped=dropped)

        upserted = RssItemRepository(db).upsert_items(kept) if kept else 0
        if kept:
            now = datetime.now(timezone.utc)
            db.query(RssItem).filter(RssItem.guid.in_([k.guid or k.url for k in kept])).update({RssItem.verified_at: now}, synchronize_session=False)
            db.commit()
        trace.step("persist", upserted=upserted)

        enriched = enrich(db, fetch=enrich_fetch)
        trace.step("enrich", pages_enriched=enriched)

        qa = ingestion_qa(db)
        trace.step("qa", **qa)

        summary = {"found": len(gathered), "kept": len(kept), "upserted": upserted, "enriched": enriched, "qa": qa, "run_id": trace.run.id}
        trace.finish("ok", summary)
        return summary
    except Exception as exc:
        db.rollback()
        trace.step("error", error=str(exc)[:300])
        trace.finish("error", {"error": str(exc)[:300]})
        raise


def default_adapters() -> dict[str, OpportunityAdapter]:
    from app.services.discovery.ats import ATSAdapter
    from app.services.discovery.devpost import DevpostAdapter
    from app.services.discovery.hn import HNHiringAdapter
    from app.services.discovery.programs import ProgramsAdapter
    return {"ats": ATSAdapter(), "hn": HNHiringAdapter(), "devpost": DevpostAdapter(), "programs": ProgramsAdapter()}
