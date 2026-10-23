from tests.conftest import make_item, register


def test_toggle_adds_then_removes(client, auth_headers, seed_items):
    (item,) = seed_items(make_item())

    first = client.post(f"/api/bookmarks/{item.id}", headers=auth_headers)
    assert first.json() == {"action": "added", "rss_item_id": item.id}

    second = client.post(f"/api/bookmarks/{item.id}", headers=auth_headers)
    assert second.json() == {"action": "removed", "rss_item_id": item.id}
    assert client.get("/api/bookmarks/ids", headers=auth_headers).json() == {"ids": []}


def test_toggle_unknown_item_is_404(client, auth_headers):
    assert client.post("/api/bookmarks/9999", headers=auth_headers).status_code == 404


def test_list_bookmarks_includes_item_id(client, auth_headers, seed_items):
    """Regression: the list must carry `id` so the bookmarks page can un-bookmark."""
    (item,) = seed_items(make_item())
    client.post(f"/api/bookmarks/{item.id}", headers=auth_headers)

    listed = client.get("/api/bookmarks", headers=auth_headers).json()
    assert [b["id"] for b in listed] == [item.id]
    assert listed[0]["title"] == item.title


def test_list_filters_by_category(client, auth_headers, seed_items):
    intern, job = seed_items(
        make_item(),
        make_item(
            title="Backend Developer Job",
            url="https://example.com/jobs/backend",
            summary="We are hiring a backend developer. Apply now.",
            category="job",
        ),
    )
    for item in (intern, job):
        client.post(f"/api/bookmarks/{item.id}", headers=auth_headers)

    jobs = client.get("/api/bookmarks?category=job", headers=auth_headers).json()
    assert [b["id"] for b in jobs] == [job.id]


def test_delete_is_idempotent(client, auth_headers, seed_items):
    (item,) = seed_items(make_item())
    client.post(f"/api/bookmarks/{item.id}", headers=auth_headers)

    for _ in range(2):
        resp = client.delete(f"/api/bookmarks/{item.id}", headers=auth_headers)
        assert resp.json()["action"] == "removed"
    assert client.get("/api/bookmarks/ids", headers=auth_headers).json() == {"ids": []}


def test_bookmarks_are_per_user(client, auth_headers, seed_items):
    (item,) = seed_items(make_item())
    client.post(f"/api/bookmarks/{item.id}", headers=auth_headers)

    other = register(client, "other@example.com")
    assert client.get("/api/bookmarks", headers=other).json() == []
