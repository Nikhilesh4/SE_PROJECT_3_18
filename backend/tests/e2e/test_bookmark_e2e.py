"""
E2E Tests — Bookmark Flow
===========================
Tests the complete bookmark lifecycle:
  Toggle bookmark → list bookmarks → list bookmark IDs → remove bookmark.
Also covers multi-user isolation and edge cases.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.rss_item import RssItem
from app.models.user import User


class TestToggleBookmark:
    """POST /api/bookmarks/{item_id} — toggle a bookmark on/off."""

    def test_toggle_adds_bookmark(
        self,
        client: TestClient,
        auth_headers: dict,
        sample_rss_items: list[RssItem],
    ):
        item_id = sample_rss_items[0].id
        resp = client.post(f"/api/bookmarks/{item_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "added"
        assert data["rss_item_id"] == item_id

    def test_toggle_removes_existing_bookmark(
        self,
        client: TestClient,
        auth_headers: dict,
        sample_rss_items: list[RssItem],
    ):
        item_id = sample_rss_items[0].id

        # Add
        client.post(f"/api/bookmarks/{item_id}", headers=auth_headers)
        # Toggle again → remove
        resp = client.post(f"/api/bookmarks/{item_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["action"] == "removed"

    def test_toggle_nonexistent_item_returns_404(
        self,
        client: TestClient,
        auth_headers: dict,
    ):
        resp = client.post("/api/bookmarks/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_toggle_requires_auth(self, client: TestClient, sample_rss_items: list[RssItem]):
        resp = client.post(f"/api/bookmarks/{sample_rss_items[0].id}")
        assert resp.status_code == 401


class TestListBookmarks:
    """GET /api/bookmarks — list all bookmarked items for the authenticated user."""

    def test_list_bookmarks_returns_bookmarked_items(
        self,
        client: TestClient,
        auth_headers: dict,
        sample_rss_items: list[RssItem],
    ):
        # Bookmark two items
        client.post(f"/api/bookmarks/{sample_rss_items[0].id}", headers=auth_headers)
        client.post(f"/api/bookmarks/{sample_rss_items[1].id}", headers=auth_headers)

        resp = client.get("/api/bookmarks", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        # Verify full item data is returned
        urls = {item["url"] for item in data}
        assert sample_rss_items[0].url in urls
        assert sample_rss_items[1].url in urls

    def test_list_bookmarks_empty_for_new_user(
        self,
        client: TestClient,
        auth_headers: dict,
    ):
        resp = client.get("/api/bookmarks", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_bookmarks_supports_category_filter(
        self,
        client: TestClient,
        auth_headers: dict,
        sample_rss_items: list[RssItem],
    ):
        # Bookmark items of different categories
        for item in sample_rss_items:
            client.post(f"/api/bookmarks/{item.id}", headers=auth_headers)

        # Filter by category
        resp = client.get("/api/bookmarks?category=job", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert all(item["category"] == "job" for item in data)


class TestListBookmarkIds:
    """GET /api/bookmarks/ids — lightweight list of bookmarked IDs."""

    def test_list_bookmark_ids(
        self,
        client: TestClient,
        auth_headers: dict,
        sample_rss_items: list[RssItem],
    ):
        # Bookmark three items
        for item in sample_rss_items[:3]:
            client.post(f"/api/bookmarks/{item.id}", headers=auth_headers)

        resp = client.get("/api/bookmarks/ids", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert set(data["ids"]) == {item.id for item in sample_rss_items[:3]}

    def test_list_bookmark_ids_empty(
        self,
        client: TestClient,
        auth_headers: dict,
    ):
        resp = client.get("/api/bookmarks/ids", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["ids"] == []


class TestRemoveBookmark:
    """DELETE /api/bookmarks/{item_id} — explicit removal (idempotent)."""

    def test_remove_existing_bookmark(
        self,
        client: TestClient,
        auth_headers: dict,
        sample_rss_items: list[RssItem],
    ):
        item_id = sample_rss_items[0].id
        client.post(f"/api/bookmarks/{item_id}", headers=auth_headers)

        resp = client.delete(f"/api/bookmarks/{item_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["action"] == "removed"

        # Verify it's gone
        ids_resp = client.get("/api/bookmarks/ids", headers=auth_headers)
        assert item_id not in ids_resp.json()["ids"]

    def test_remove_nonexistent_bookmark_is_idempotent(
        self,
        client: TestClient,
        auth_headers: dict,
        sample_rss_items: list[RssItem],
    ):
        """Removing a bookmark that doesn't exist should succeed silently."""
        resp = client.delete(f"/api/bookmarks/{sample_rss_items[0].id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["action"] == "removed"


class TestBookmarkMultiUserIsolation:
    """Ensure bookmarks are per-user and don't leak across accounts."""

    def test_users_see_only_their_own_bookmarks(
        self,
        client: TestClient,
        auth_headers: dict,
        second_auth_headers: dict,
        sample_rss_items: list[RssItem],
    ):
        # User 1 bookmarks item 0
        client.post(f"/api/bookmarks/{sample_rss_items[0].id}", headers=auth_headers)
        # User 2 bookmarks item 1
        client.post(f"/api/bookmarks/{sample_rss_items[1].id}", headers=second_auth_headers)

        # User 1 should only see their bookmark
        resp1 = client.get("/api/bookmarks/ids", headers=auth_headers)
        assert resp1.json()["ids"] == [sample_rss_items[0].id]

        # User 2 should only see their bookmark
        resp2 = client.get("/api/bookmarks/ids", headers=second_auth_headers)
        assert resp2.json()["ids"] == [sample_rss_items[1].id]
