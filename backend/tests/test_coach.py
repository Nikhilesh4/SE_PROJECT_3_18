import json
from datetime import datetime, timedelta, timezone

import httpx

from app.config import settings
from app.db import SessionLocal
from app.models.activity import AgentRun
from app.services import llm
from app.services.digest import build_digest, send_due_digests
from tests.conftest import make_item, register

NOW = datetime.now(timezone.utc)


def test_outreach_templates_for_every_kind(client, with_profile, seed_items):
    (item,) = seed_items(make_item(title="Python Backend Intern", author="Acme", summary="Python and Docker."))
    for kind in ("cold_email", "linkedin_note", "referral_request", "follow_up"):
        d = client.post("/api/outreach/draft", headers=with_profile, json={"kind": kind, "item_id": item.id, "recipient": "Priya"}).json()
        assert d["generated_by"] == "template" and "Priya" in d["body"] and "Acme" in d["body"] and "draft" in d["review_note"].lower()
    note = client.post("/api/outreach/draft", headers=with_profile, json={"kind": "linkedin_note", "item_id": item.id}).json()
    assert len(note["body"]) <= 300 and "python" in note["body"].lower()
    assert client.post("/api/outreach/draft", headers=with_profile, json={"kind": "spam"}).status_code == 422
    assert client.post("/api/outreach/draft", headers=with_profile, json={"kind": "cold_email", "item_id": 999}).status_code == 404
    assert client.post("/api/outreach/draft", json={"kind": "cold_email"}).status_code == 401


def test_outreach_uses_llm_when_available_and_ignores_garbage(client, with_profile, seed_items, monkeypatch):
    (item,) = seed_items(make_item(author="Acme"))
    monkeypatch.setattr(llm, "complete_sync", lambda s, p: json.dumps({"subject": "Hello", "body": "Polished body"}))
    d = client.post("/api/outreach/draft", headers=with_profile, json={"kind": "cold_email", "item_id": item.id}).json()
    assert d["generated_by"] == "llm" and d["body"] == "Polished body"
    monkeypatch.setattr(llm, "complete_sync", lambda s, p: "not json at all")
    assert client.post("/api/outreach/draft", headers=with_profile, json={"kind": "cold_email", "item_id": item.id}).json()["generated_by"] == "template"


def test_interview_questions_and_feedback(client, with_profile, seed_items):
    (item,) = seed_items(make_item(title="Python SQL Intern", summary="Use Python and SQL."))
    q = client.post("/api/interview/questions", headers=with_profile, json={"item_id": item.id}).json()
    topics = {x["topic"] for x in q["questions"]}
    assert {"python", "sql", "behavioural"} <= topics and q["generated_by"] == "question-bank"
    assert client.post("/api/interview/questions", headers=with_profile, json={}).status_code == 422

    weak = client.post("/api/interview/feedback", headers=with_profile, json={"question": "Tell me about a project", "answer": "It was fine."}).json()
    assert not weak["checks"]["right_length"] and len(weak["tips"]) >= 2
    strong_answer = "For example, in my project I built an API with Python. " + "I used caching and tests to keep it reliable. " * 4 + "The result was a 40% latency improvement."
    strong = client.post("/api/interview/feedback", headers=with_profile, json={"question": "Tell me about a project", "answer": strong_answer}).json()
    assert all(strong["checks"].values())


def test_projects_company_and_reverse_search(client, with_profile, seed_items):
    from app.services.matching.semantic import embed_pending_items, embed_pending_profiles
    a, b = seed_items(
        make_item(url="https://e.com/1", title="Python Intern", author="Acme", summary="Python, Docker, Kubernetes. ₹30,000/month"),
        make_item(url="https://e.com/2", title="Frontend Intern", author="Beta", summary="React and CSS."),
    )
    proj = client.get(f"/api/insights/projects?item_id={a.id}", headers=with_profile).json()
    assert set(proj["missing"]) == {"docker", "kubernetes"} and len(proj["projects"]) == 2

    brief = client.get("/api/insights/company?name=acme", headers=with_profile).json()
    assert brief["open_postings"] == 1 and brief["median_stipend_inr_month"] == 30000
    assert {s["skill"]: s["you_have"] for s in brief["skills_in_demand"]}["python"] is True
    assert client.get("/api/insights/company?name=nobody", headers=with_profile).json()["open_postings"] == 0

    embed_pending_items(); embed_pending_profiles()
    companies = client.get("/api/insights/companies", headers=with_profile).json()["companies"]
    assert {c["company"] for c in companies} == {"Acme", "Beta"}


def test_memory_searches_own_notes_only(client, auth_headers, seed_items):
    (item,) = seed_items(make_item(title="Backend Intern"))
    client.post(f"/api/bookmarks/{item.id}", headers=auth_headers)
    client.patch(f"/api/applications/{item.id}", headers=auth_headers, json={"notes": "Recruiter Maya said the interview covers graph algorithms"})
    hits = client.get("/api/memory/search?q=graph algorithms", headers=auth_headers).json()["results"]
    assert hits[0]["item_id"] == item.id and "Maya" in hits[0]["notes"]
    other = register(client, "o@example.com")
    assert client.get("/api/memory/search?q=graph", headers=other).json()["results"] == []


def test_research_scout_endpoint_and_draft(client, auth_headers, monkeypatch):
    from app.services.discovery import scholarly
    monkeypatch.setattr(scholarly, "scout", lambda topic, **kw: {"topic": topic, "papers": [], "errors": [], "contacts": [{"name": "Ada Lovelace", "papers": ["Fast Transformers"], "affiliations": [], "homepage": None, "s2_author_id": None}]})
    out = client.post("/api/research/scout", headers=auth_headers, json={"topic": "attention", "draft_for": "Ada Lovelace"}).json()
    assert "Professor Lovelace" in out["draft"]["body"] and "review_note" in out["draft"]
    assert client.post("/api/research/scout", headers=auth_headers, json={"topic": "attention", "draft_for": "Nobody"}).status_code == 404


def test_admin_endpoints_require_admin_email(client, auth_headers, monkeypatch):
    assert client.get("/api/discovery/runs", headers=auth_headers).status_code == 403
    monkeypatch.setattr(settings, "ADMIN_EMAILS", "student@example.com")
    db = SessionLocal()
    try:
        db.add(AgentRun(kind="discovery", status="ok", steps=[{"stage": "plan"}], output={"found": 1}))
        db.commit()
    finally:
        db.close()
    runs = client.get("/api/discovery/runs", headers=auth_headers).json()["runs"]
    assert runs[0]["output"] == {"found": 1} and runs[0]["steps"][0]["stage"] == "plan"


def test_digest_summarises_tracker_and_is_sent_once_per_week(client, with_profile, seed_items):
    soon, old = seed_items(
        make_item(url="https://e.com/1", title="Closing Soon Role", application_deadline=NOW + timedelta(days=3)),
        make_item(url="https://e.com/2", title="Applied Long Ago"),
    )
    for i in (soon, old):
        client.post(f"/api/bookmarks/{i.id}", headers=with_profile)
    client.patch(f"/api/applications/{old.id}", headers=with_profile, json={"status": "applied"})

    db = SessionLocal()
    try:
        from app.models.bookmark import Bookmark
        db.query(Bookmark).filter(Bookmark.rss_item_id == old.id).update({Bookmark.updated_at: NOW - timedelta(days=20)})
        db.commit()
        uid = db.query(Bookmark.user_id).first()[0]
        d = build_digest(db, uid)
        assert d["facts"]["saved"] == 1 and d["facts"]["applied"] == 1 and d["facts"]["closing_soon"] == ["Closing Soon Role"]
        assert any("Follow up" in a for a in d["facts"]["actions"]) and any("Closing Soon Role" in a for a in d["facts"]["actions"])
        assert send_due_digests(db) == 1 and send_due_digests(db) == 0
    finally:
        db.close()
    assert client.get("/api/notifications", headers=with_profile).json()["notifications"][0]["kind"] == "digest"


def _track(client, headers, item, status=None):
    client.post(f"/api/bookmarks/{item.id}", headers=headers)
    if status:
        client.patch(f"/api/applications/{item.id}", headers=headers, json={"status": status})


def test_standup_endpoint_ranks_actions_and_caps_at_three(client, with_profile, seed_items):
    deadline, interview, applied = seed_items(
        make_item(url="https://e.com/d", title="Closing Role", application_deadline=NOW + timedelta(days=2)),
        make_item(url="https://e.com/i", title="Interview Role"),
        make_item(url="https://e.com/a", title="Applied Role"),
    )
    _track(client, with_profile, deadline)
    _track(client, with_profile, interview, "interview")
    _track(client, with_profile, applied, "applied")
    db = SessionLocal()
    try:
        from app.models.bookmark import Bookmark
        db.query(Bookmark).filter(Bookmark.rss_item_id == applied.id).update({Bookmark.updated_at: NOW - timedelta(days=30)})
        db.commit()
    finally:
        db.close()

    data = client.get("/api/standup", headers=with_profile).json()
    kinds = [a["kind"] for a in data["actions"]]
    assert kinds == ["deadline", "interview", "follow_up"]  # priority order, capped at 3
    assert data["actions"][0]["item_id"] == deadline.id and "Closing Role" in data["actions"][0]["text"]
    assert data["facts"]["saved"] == 1 and data["facts"]["interview"] == 1 and data["facts"]["stale_applications"] == 1
    assert "Closing Role" in data["text"]


def test_standup_asks_for_a_resume_first_when_there_is_no_profile(client, auth_headers):
    data = client.get("/api/standup", headers=auth_headers).json()
    assert data["actions"][0]["kind"] == "profile" and data["facts"]["has_profile"] is False


def test_standup_surfaces_a_recurring_skill_gap(client, with_profile, seed_items):
    a, b = seed_items(
        make_item(url="https://e.com/k1", title="Platform Intern", summary="Kubernetes and Docker experience required."),
        make_item(url="https://e.com/k2", title="DevOps Intern", summary="You will use Kubernetes daily."),
    )
    _track(client, with_profile, a)
    _track(client, with_profile, b)
    acts = client.get("/api/standup", headers=with_profile).json()["actions"]
    gap = [x for x in acts if x["kind"] == "skill_gap"]
    assert gap and "kubernetes" in gap[0]["text"].lower() and "2 of your 2" in gap[0]["text"]


def test_standup_requires_login(client):
    assert client.get("/api/standup").status_code == 401
