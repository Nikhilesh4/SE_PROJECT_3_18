from datetime import datetime, timedelta, timezone

from app.services.matching.semantic import embed_pending_items, embed_pending_profiles
from app.services.notify import notify_deadlines, notify_new_matches
from app.db import SessionLocal
from tests.conftest import make_item, register

NOW = datetime.now(timezone.utc)


def _save(client, headers, item):
    client.post(f"/api/bookmarks/{item.id}", headers=headers)


# ── application tracker ──────────────────────────────────────────────────────

def test_board_groups_by_status_and_tracks_applied_at(client, auth_headers, seed_items):
    a, b = seed_items(make_item(), make_item(url="https://example.com/b", title="Other"))
    _save(client, auth_headers, a); _save(client, auth_headers, b)

    board = client.get("/api/applications", headers=auth_headers).json()
    assert board["statuses"] == ["saved", "applied", "interview", "offer", "rejected"]
    assert len(board["columns"]["saved"]) == 2

    moved = client.patch(f"/api/applications/{a.id}", headers=auth_headers,
                         json={"status": "applied", "notes": "Sent via referral"}).json()
    assert moved["status"] == "applied" and moved["applied_at"] and moved["notes"] == "Sent via referral"

    board = client.get("/api/applications", headers=auth_headers).json()
    assert [c["item"]["id"] for c in board["columns"]["applied"]] == [a.id]
    assert [c["item"]["id"] for c in board["columns"]["saved"]] == [b.id]


def test_application_update_validates_and_requires_bookmark(client, auth_headers, seed_items):
    (a,) = seed_items(make_item())
    assert client.patch(f"/api/applications/{a.id}", headers=auth_headers, json={"status": "applied"}).status_code == 404
    _save(client, auth_headers, a)
    assert client.patch(f"/api/applications/{a.id}", headers=auth_headers, json={"status": "dancing"}).status_code == 422
    other = register(client, "other@example.com")
    assert client.patch(f"/api/applications/{a.id}", headers=other, json={"status": "applied"}).status_code == 404


# ── deadlines + calendar ─────────────────────────────────────────────────────

def test_deadlines_and_ics_export(client, auth_headers, seed_items):
    soon, later, none = seed_items(
        make_item(url="https://e.com/soon", title="Soon", application_deadline=NOW + timedelta(days=2)),
        make_item(url="https://e.com/later", title="Later", application_deadline=NOW + timedelta(days=60)),
        make_item(url="https://e.com/none", title="None"),
    )
    for i in (soon, later, none):
        _save(client, auth_headers, i)

    due = client.get("/api/deadlines?days=7", headers=auth_headers).json()["items"]
    assert [i["id"] for i in due] == [soon.id] and due[0]["days_left"] in (1, 2)

    resp = client.get("/api/bookmarks/calendar.ics", headers=auth_headers)
    assert resp.headers["content-type"].startswith("text/calendar")
    assert resp.text.count("BEGIN:VEVENT") == 2

    # Once applied, a deadline no longer nags.
    client.patch(f"/api/applications/{soon.id}", headers=auth_headers, json={"status": "applied"})
    assert client.get("/api/deadlines?days=7", headers=auth_headers).json()["items"] == []


# ── notifications ────────────────────────────────────────────────────────────

def test_deadline_notification_is_created_once(client, auth_headers, seed_items):
    (soon,) = seed_items(make_item(application_deadline=NOW + timedelta(days=2)))
    _save(client, auth_headers, soon)
    db = SessionLocal()
    try:
        assert notify_deadlines(db) == 1
        assert notify_deadlines(db) == 0
    finally:
        db.close()
    data = client.get("/api/notifications", headers=auth_headers).json()
    assert data["unread"] == 1 and data["notifications"][0]["kind"] == "deadline"

    client.post("/api/notifications/read", headers=auth_headers, json={})
    assert client.get("/api/notifications?unread_only=true", headers=auth_headers).json()["unread"] == 0


def test_new_match_notifications_use_profile_embedding(client, with_profile, seed_items):
    # with_profile's skills are Python/SQL; add a profile whose interest is ML.
    ml, css = seed_items(
        make_item(url="https://e.com/ml", title="Machine learning intern", summary="Train neural networks with PyTorch."),
        make_item(url="https://e.com/css", title="Frontend intern", summary="React and CSS UI work."),
    )
    from app.repositories.profile_repository import ProfileRepository
    from app.schemas.profile import ProfileStructured
    db = SessionLocal()
    try:
        from app.models.profile import Profile
        uid = db.query(Profile).first().user_id
        ProfileRepository().upsert_profile(db, uid, raw_text="r", parsed_profile=ProfileStructured(skills=["machine learning", "pytorch"], interests=["neural"]))
    finally:
        db.close()
    embed_pending_items(); embed_pending_profiles()

    db = SessionLocal()
    try:
        assert notify_new_matches(db, threshold=0.3) >= 1
        assert notify_new_matches(db, threshold=0.3) == 0  # deduped
    finally:
        db.close()
    titles = [n["title"] for n in client.get("/api/notifications", headers=with_profile).json()["notifications"]]
    assert any("Machine learning" in t for t in titles) and not any("Frontend" in t for t in titles)


def test_notifications_are_private(client, auth_headers, seed_items):
    (soon,) = seed_items(make_item(application_deadline=NOW + timedelta(days=1)))
    _save(client, auth_headers, soon)
    db = SessionLocal()
    try:
        notify_deadlines(db)
    finally:
        db.close()
    other = register(client, "other@example.com")
    assert client.get("/api/notifications", headers=other).json() == {"unread": 0, "notifications": []}


# ── feedback / search / insights ─────────────────────────────────────────────

def test_hidden_items_leave_the_feed_for_that_user_only(client, auth_headers, seed_items):
    a, b = seed_items(make_item(), make_item(url="https://example.com/b", title="Second Role"))
    client.get("/api/feeds/rss", headers=auth_headers)  # warm the shared cache
    assert client.post(f"/api/feedback/{a.id}", headers=auth_headers, json={"value": "hide"}).status_code == 200

    mine = client.get("/api/feeds/rss", headers=auth_headers).json()["items"]
    assert [i["id"] for i in mine] == [b.id]
    anon = client.get("/api/feeds/rss").json()["items"]
    assert {i["id"] for i in anon} == {a.id, b.id}

    assert client.post(f"/api/feedback/{a.id}", headers=auth_headers, json={"value": "nope"}).status_code == 422
    client.delete(f"/api/feedback/{a.id}", headers=auth_headers)
    assert len(client.get("/api/feeds/rss", headers=auth_headers).json()["items"]) == 2


def test_search_facets_and_filters(client, seed_items):
    seed_items(
        make_item(url="https://e.com/1", title="Remote Python intern", summary="Fully remote. Stipend ₹30,000/month. Python and Django."),
        make_item(url="https://e.com/2", title="Onsite Java intern", summary="On-site only. Stipend ₹10,000/month. Java and Spring."),
        make_item(url="https://e.com/3", title="Hackathon sprint", category="hackathon", summary="Build anything, win prizes."),
    )
    r = client.get("/api/search?q=python").json()
    assert [i["title"] for i in r["items"]] == ["Remote Python intern"]
    assert r["items"][0]["remote"] and r["items"][0]["stipend_inr_month"] == 30000

    assert client.get("/api/search?remote=true").json()["total"] == 1
    assert client.get("/api/search?min_stipend=20000").json()["total"] == 1
    cats = client.get("/api/search").json()["facets"]["categories"]
    assert cats == {"internship": 2, "hackathon": 1}


def test_item_insights_explain_skill_gap_and_scam(client, with_profile, seed_items):
    (item,) = seed_items(make_item(
        title="Python Backend Intern",
        summary="Use Python, Docker and Kubernetes. Pay a registration fee. Contact on WhatsApp only. Class of 2026. CGPA 8.",
    ))
    d = client.get(f"/api/insights/items/{item.id}", headers=with_profile).json()
    assert d["skill_gap"]["matched"] == ["python"] and set(d["skill_gap"]["missing"]) == {"docker", "kubernetes"}
    assert d["skill_gap"]["coverage"] == 33
    assert d["ranking"]["matched_in_title"] == ["Python"]
    assert d["scam"]["risky"] and d["eligibility"]["years"] == [2026]
    assert client.get("/api/insights/items/9999", headers=with_profile).status_code == 404


def test_trends_count_skills_and_stipends(client, seed_items):
    seed_items(
        make_item(url="https://e.com/1", title="A", summary="Python and SQL. ₹20,000/month"),
        make_item(url="https://e.com/2", title="B", summary="Python and React. ₹40,000/month"),
    )
    t = client.get("/api/insights/trends").json()
    assert t["top_skills"][0] == {"skill": "python", "postings": 2}
    assert t["stipend_inr_month"]["internship"]["median"] == 30000
