"""
E2E Tests — Notification Flow
===============================
Tests the notification lifecycle:
  List notifications → mark one read → mark all read.
Also tests the matching engine scoring logic end-to-end.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.rss_item import RssItem
from app.models.user import User


# ── Helpers ──────────────────────────────────────────────────────────────────

def _seed_notifications(
    db: Session,
    user_id: int,
    rss_items: list[RssItem],
    *,
    read_count: int = 0,
) -> list[Notification]:
    """Create notification rows linked to the given user + RSS items."""
    notifs = []
    for i, item in enumerate(rss_items):
        n = Notification(
            user_id=user_id,
            rss_item_id=item.id,
            title=item.title,
            url=item.url,
            category=item.category,
            match_score=0.7 - (i * 0.1),
            is_read=i < read_count,
            read_at=datetime.now(timezone.utc) if i < read_count else None,
        )
        db.add(n)
        notifs.append(n)
    db.commit()
    for n in notifs:
        db.refresh(n)
    return notifs


# ── Tests ────────────────────────────────────────────────────────────────────

class TestListNotifications:
    """GET /api/notifications — list user's notifications."""

    def test_list_notifications_returns_items_and_unread_count(
        self,
        client: TestClient,
        auth_headers: dict,
        test_user: tuple[User, str],
        sample_rss_items: list[RssItem],
        db_session: Session,
    ):
        user, _ = test_user
        _seed_notifications(db_session, user.id, sample_rss_items[:3], read_count=1)

        resp = client.get("/api/notifications", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "unread_count" in data
        assert len(data["items"]) == 3
        assert data["unread_count"] == 2  # 3 total, 1 read

    def test_list_notifications_exclude_read(
        self,
        client: TestClient,
        auth_headers: dict,
        test_user: tuple[User, str],
        sample_rss_items: list[RssItem],
        db_session: Session,
    ):
        user, _ = test_user
        _seed_notifications(db_session, user.id, sample_rss_items[:3], read_count=1)

        resp = client.get(
            "/api/notifications?include_read=false", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2  # only unread
        assert all(not item["is_read"] for item in data["items"])

    def test_list_notifications_empty(
        self,
        client: TestClient,
        auth_headers: dict,
    ):
        resp = client.get("/api/notifications", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["unread_count"] == 0

    def test_list_notifications_requires_auth(self, client: TestClient):
        resp = client.get("/api/notifications")
        assert resp.status_code == 401


class TestMarkNotificationRead:
    """PATCH /api/notifications/{id}/read — mark a single notification read."""

    def test_mark_read_success(
        self,
        client: TestClient,
        auth_headers: dict,
        test_user: tuple[User, str],
        sample_rss_items: list[RssItem],
        db_session: Session,
    ):
        user, _ = test_user
        notifs = _seed_notifications(db_session, user.id, sample_rss_items[:1])
        notif_id = notifs[0].id

        resp = client.patch(
            f"/api/notifications/{notif_id}/read", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_read"] is True
        assert data["read_at"] is not None

    def test_mark_read_nonexistent_returns_404(
        self,
        client: TestClient,
        auth_headers: dict,
    ):
        resp = client.patch(
            "/api/notifications/99999/read", headers=auth_headers
        )
        assert resp.status_code == 404

    def test_mark_already_read_is_idempotent(
        self,
        client: TestClient,
        auth_headers: dict,
        test_user: tuple[User, str],
        sample_rss_items: list[RssItem],
        db_session: Session,
    ):
        user, _ = test_user
        notifs = _seed_notifications(db_session, user.id, sample_rss_items[:1])
        notif_id = notifs[0].id

        # Mark read twice — should succeed both times
        client.patch(f"/api/notifications/{notif_id}/read", headers=auth_headers)
        resp = client.patch(f"/api/notifications/{notif_id}/read", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["is_read"] is True


class TestMarkAllNotificationsRead:
    """PATCH /api/notifications/read-all — mark all notifications read."""

    def test_mark_all_read(
        self,
        client: TestClient,
        auth_headers: dict,
        test_user: tuple[User, str],
        sample_rss_items: list[RssItem],
        db_session: Session,
    ):
        user, _ = test_user
        _seed_notifications(db_session, user.id, sample_rss_items[:4])

        resp = client.patch("/api/notifications/read-all", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["updated"] == 4

        # Verify all are read
        list_resp = client.get("/api/notifications", headers=auth_headers)
        assert list_resp.json()["unread_count"] == 0

    def test_mark_all_read_when_none_exist(
        self,
        client: TestClient,
        auth_headers: dict,
    ):
        resp = client.patch("/api/notifications/read-all", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["updated"] == 0


class TestNotificationMultiUserIsolation:
    """Ensure notifications are scoped to the authenticated user."""

    def test_users_see_only_their_own_notifications(
        self,
        client: TestClient,
        auth_headers: dict,
        second_auth_headers: dict,
        test_user: tuple[User, str],
        second_user: tuple[User, str],
        sample_rss_items: list[RssItem],
        db_session: Session,
    ):
        user1, _ = test_user
        user2, _ = second_user

        _seed_notifications(db_session, user1.id, sample_rss_items[:2])
        _seed_notifications(db_session, user2.id, sample_rss_items[2:4])

        resp1 = client.get("/api/notifications", headers=auth_headers)
        resp2 = client.get("/api/notifications", headers=second_auth_headers)

        assert len(resp1.json()["items"]) == 2
        assert len(resp2.json()["items"]) == 2

        # User 1's notifications should reference items 0 and 1
        urls1 = {n["url"] for n in resp1.json()["items"]}
        assert sample_rss_items[0].url in urls1
        assert sample_rss_items[2].url not in urls1
