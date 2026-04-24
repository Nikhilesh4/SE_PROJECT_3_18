"""
E2E Tests — Full User Journey
================================
Tests complete multi-step user flows that span multiple API domains:
  1. Register → Login → Access protected resource
  2. Register → Bookmark items → List bookmarks → Remove bookmark
  3. Register → Get feed → Bookmark from feed → Verify in bookmark list
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.rss_item import RssItem
from app.schemas.rss_item import NormalizedRssItem, RssAggregationResponse


class TestFullRegistrationToBookmarkFlow:
    """
    Complete journey: Register → Bookmark → List → Remove → Verify removed.
    """

    def test_register_bookmark_list_remove(
        self,
        client: TestClient,
        sample_rss_items: list[RssItem],
    ):
        # Step 1: Register a new user
        reg_resp = client.post("/auth/register", json={
            "name": "Journey User",
            "email": "journey@test.com",
            "password": "journeypass",
            "skills": ["python"],
        })
        assert reg_resp.status_code == 201
        token = reg_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Step 2: Bookmark two items
        item1_id = sample_rss_items[0].id
        item2_id = sample_rss_items[1].id

        r1 = client.post(f"/api/bookmarks/{item1_id}", headers=headers)
        assert r1.json()["action"] == "added"

        r2 = client.post(f"/api/bookmarks/{item2_id}", headers=headers)
        assert r2.json()["action"] == "added"

        # Step 3: List bookmarks — should have 2
        list_resp = client.get("/api/bookmarks", headers=headers)
        assert len(list_resp.json()) == 2

        # Step 4: Remove one bookmark
        client.delete(f"/api/bookmarks/{item1_id}", headers=headers)

        # Step 5: Verify only one remains
        list_resp2 = client.get("/api/bookmarks", headers=headers)
        assert len(list_resp2.json()) == 1
        assert list_resp2.json()[0]["url"] == sample_rss_items[1].url

        # Step 6: IDs endpoint should match
        ids_resp = client.get("/api/bookmarks/ids", headers=headers)
        assert ids_resp.json()["ids"] == [item2_id]


class TestLoginAndAccessFlow:
    """
    Full flow: Register → Logout (no session) → Login → Access protected resource.
    """

    def test_register_then_login_then_access(self, client: TestClient):
        # Register
        client.post("/auth/register", json={
            "name": "Flow User",
            "email": "flow@test.com",
            "password": "flowpass",
        })

        # Login
        login_resp = client.post("/auth/login", json={
            "email": "flow@test.com",
            "password": "flowpass",
        })
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]

        # Access protected resource
        headers = {"Authorization": f"Bearer {token}"}
        # /profile/me returns 404 because no profile uploaded — but auth succeeded
        profile_resp = client.get("/profile/me", headers=headers)
        assert profile_resp.status_code == 404


class TestBookmarkToggleRoundTrip:
    """Verify the toggle behavior: add → remove → add cycle."""

    def test_toggle_add_remove_add(
        self,
        client: TestClient,
        auth_headers: dict,
        sample_rss_items: list[RssItem],
    ):
        item_id = sample_rss_items[0].id

        # Toggle 1: Add
        r1 = client.post(f"/api/bookmarks/{item_id}", headers=auth_headers)
        assert r1.json()["action"] == "added"

        # Toggle 2: Remove
        r2 = client.post(f"/api/bookmarks/{item_id}", headers=auth_headers)
        assert r2.json()["action"] == "removed"

        # Toggle 3: Add again
        r3 = client.post(f"/api/bookmarks/{item_id}", headers=auth_headers)
        assert r3.json()["action"] == "added"

        # Final state: bookmarked
        ids = client.get("/api/bookmarks/ids", headers=auth_headers).json()["ids"]
        assert item_id in ids


class TestNotificationToMarkReadFlow:
    """
    Journey: Seed notifications → List → Mark one read → Mark all read.
    """

    def test_notification_read_workflow(
        self,
        client: TestClient,
        auth_headers: dict,
        test_user,
        sample_rss_items: list[RssItem],
        db_session: Session,
    ):
        from app.models.notification import Notification

        user, _ = test_user

        # Seed 3 unread notifications
        for i, item in enumerate(sample_rss_items[:3]):
            db_session.add(Notification(
                user_id=user.id,
                rss_item_id=item.id,
                title=item.title,
                url=item.url,
                category=item.category,
                match_score=0.8,
                is_read=False,
            ))
        db_session.commit()

        # Step 1: List — 3 unread
        resp = client.get("/api/notifications", headers=auth_headers)
        assert resp.json()["unread_count"] == 3
        notif_id = resp.json()["items"][0]["id"]

        # Step 2: Mark one read
        mark_resp = client.patch(
            f"/api/notifications/{notif_id}/read", headers=auth_headers
        )
        assert mark_resp.json()["is_read"] is True

        # Step 3: Verify unread count decreased
        resp2 = client.get("/api/notifications", headers=auth_headers)
        assert resp2.json()["unread_count"] == 2

        # Step 4: Mark all read
        client.patch("/api/notifications/read-all", headers=auth_headers)

        # Step 5: Verify all read
        resp3 = client.get("/api/notifications", headers=auth_headers)
        assert resp3.json()["unread_count"] == 0
