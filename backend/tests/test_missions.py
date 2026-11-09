from datetime import datetime, timedelta, timezone

from app.db import SessionLocal
from app.models.activity import Mission
from app.services.matching.semantic import embed_pending_items
from app.services.missions import run_due_missions
from tests.conftest import make_item, register

NOW = datetime.now(timezone.utc)


def _seed(seed_items):
    return seed_items(
        make_item(url="https://e.com/ml", title="Remote machine learning intern", summary="Fully remote. ₹30,000/month. Train neural networks."),
        make_item(url="https://e.com/ml2", title="Onsite machine learning intern", summary="On-site only. ₹30,000/month. Train neural networks."),
        make_item(url="https://e.com/fe", title="Frontend intern", summary="Remote. ₹30,000/month. React and CSS."),
        make_item(url="https://e.com/hack", title="ML hackathon", category="hackathon", summary="Remote neural network hackathon."),
    )


def test_mission_is_parsed_run_and_reports_only_new(client, auth_headers, seed_items):
    ml, onsite, fe, hack = _seed(seed_items)
    embed_pending_items()

    m = client.post("/api/missions", headers=auth_headers, json={
        "name": "ML", "query": "remote paid machine learning internships at least 20k per month"}).json()
    assert m["category"] == "internship" and m["remote_only"] and m["min_stipend"] == 20000

    first = client.post(f"/api/missions/{m['id']}/run", headers=auth_headers).json()["new_matches"]
    assert [x["id"] for x in first] == [ml.id]     # not on-site, not frontend, not a hackathon
    assert client.post(f"/api/missions/{m['id']}/run", headers=auth_headers).json()["new_matches"] == []

    assert [x["id"] for x in client.get(f"/api/missions/{m['id']}/matches", headers=auth_headers).json()["matches"]] == [ml.id]
    notes = client.get("/api/notifications", headers=auth_headers).json()["notifications"]
    assert notes[0]["kind"] == "mission" and "1 new match" in notes[0]["title"]

    # A later posting shows up on the next run.
    (new,) = seed_items(make_item(url="https://e.com/ml3", title="Another remote machine learning intern", summary="Remote. ₹50,000/month neural networks."))
    embed_pending_items()
    assert [x["id"] for x in client.post(f"/api/missions/{m['id']}/run", headers=auth_headers).json()["new_matches"]] == [new.id]


def test_mission_keyword_fallback_without_model(client, auth_headers, seed_items, no_embedder):
    ml, *_ = _seed(seed_items)
    m = client.post("/api/missions", headers=auth_headers, json={"name": "ML", "query": "remote machine learning internship"}).json()
    ids = [x["id"] for x in client.post(f"/api/missions/{m['id']}/run", headers=auth_headers).json()["new_matches"]]
    assert ml.id in ids


def test_missions_are_per_user_and_limited(client, auth_headers):
    m = client.post("/api/missions", headers=auth_headers, json={"name": "x", "query": "any ml jobs"}).json()
    other = register(client, "other@example.com")
    assert client.post(f"/api/missions/{m['id']}/run", headers=other).status_code == 404
    assert client.delete(f"/api/missions/{m['id']}", headers=other).status_code == 404
    assert client.patch(f"/api/missions/{m['id']}", headers=auth_headers, json={"active": False}).json()["active"] is False
    for i in range(9):
        assert client.post("/api/missions", headers=auth_headers, json={"name": f"m{i}", "query": "something else"}).status_code == 201
    assert client.post("/api/missions", headers=auth_headers, json={"name": "over", "query": "too many"}).status_code == 409


def test_due_missions_run_for_active_only(client, auth_headers, seed_items):
    _seed(seed_items); embed_pending_items()
    a = client.post("/api/missions", headers=auth_headers, json={"name": "a", "query": "machine learning"}).json()
    b = client.post("/api/missions", headers=auth_headers, json={"name": "b", "query": "machine learning"}).json()
    client.patch(f"/api/missions/{b['id']}", headers=auth_headers, json={"active": False})
    db = SessionLocal()
    try:
        assert run_due_missions(db) > 0
        assert db.get(Mission, a["id"]).last_run_at is not None
        assert db.get(Mission, b["id"]).last_run_at is None
        assert run_due_missions(db) == 0  # not due again within 24h
    finally:
        db.close()
