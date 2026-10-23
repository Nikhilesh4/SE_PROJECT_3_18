from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from app.routers.feeds import _build_skills_hash, _relevance_score
from tests.conftest import make_item


# ── Pure scoring logic ───────────────────────────────────────────────────────

def test_relevance_score_weights():
    item = make_item(
        title="Python Developer Intern",
        summary="Work with docker and kubernetes.",
        tags=["Python", "AWS"],
    )
    # python: tag (+4) + title (+2) + summary miss; docker: summary (+1); aws: tag (+4)
    assert _relevance_score(item, {"python", "docker", "aws"}) == 11
    assert _relevance_score(item, set()) == 0


def test_short_skills_ignored_in_summary():
    item = make_item(summary="Knowledge of c and go is a plus.")
    assert _relevance_score(item, {"c", "go"}) == 0


def test_skills_hash_is_order_and_case_insensitive():
    assert _build_skills_hash(["Python", " React "]) == _build_skills_hash(["react", "python"])
    assert _build_skills_hash(["python"]) != _build_skills_hash(["java"])


# ── Endpoint behaviour ───────────────────────────────────────────────────────

def test_default_feed_lists_active_items_with_ids(client, seed_items):
    stored = seed_items(make_item())
    body = client.get("/api/feeds/rss").json()
    assert body["total_items"] == 1
    assert body["items"][0]["id"] == stored[0].id
    assert body["from_cache"] is False


def test_expired_items_hidden_unless_requested(client, seed_items):
    seed_items(
        make_item(application_deadline=datetime.now(timezone.utc) - timedelta(days=1))
    )
    assert client.get("/api/feeds/rss").json()["total_items"] == 0
    assert client.get("/api/feeds/rss?active_only=false").json()["total_items"] == 1


def test_relevance_mode_ranks_matching_item_first(client, seed_items):
    newer, older = seed_items(
        make_item(url="https://example.com/a", title="Frontend Intern"),
        make_item(
            url="https://example.com/b",
            title="Python Intern",
            tags=["python"],
            published_at=datetime.now(timezone.utc) - timedelta(days=5),
        ),
    )
    default_ids = [i["id"] for i in client.get("/api/feeds/rss").json()["items"]]
    ranked_ids = [i["id"] for i in client.get("/api/feeds/rss?skills=Python").json()["items"]]
    assert default_ids == [newer.id, older.id]
    assert ranked_ids == [older.id, newer.id]


def test_second_request_served_from_cache(client, seed_items):
    seed_items(make_item())
    assert client.get("/api/feeds/rss").json()["from_cache"] is False
    assert client.get("/api/feeds/rss").json()["from_cache"] is True


def test_get_item_by_guid_and_by_url(client, seed_items):
    with_guid, without_guid = seed_items(
        make_item(url="https://example.com/g", guid="guid-123"),
        make_item(url="https://example.com/u?ref=feed"),
    )
    assert client.get("/api/feeds/rss/guid-123").json()["id"] == with_guid.id
    by_url = client.get(f"/api/feeds/rss/{quote(without_guid.url, safe='')}")
    assert by_url.status_code == 200
    assert by_url.json()["id"] == without_guid.id


def test_get_item_includes_expired_items(client, seed_items):
    """The detail page must still open items that are past their deadline."""
    seed_items(
        make_item(guid="old", application_deadline=datetime.now(timezone.utc) - timedelta(days=3))
    )
    assert client.get("/api/feeds/rss/old").status_code == 200


def test_get_unknown_item_is_404(client, db):
    assert client.get("/api/feeds/rss/does-not-exist").status_code == 404


def test_get_item_by_numeric_id(client, seed_items):
    (item,) = seed_items(make_item())
    resp = client.get(f"/api/feeds/items/{item.id}")
    assert resp.status_code == 200
    assert resp.json()["url"] == item.url
    assert client.get("/api/feeds/items/99999").status_code == 404
