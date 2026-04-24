"""
E2E Tests — Authentication Flow
================================
Tests the complete user registration and login journey:
  Register → auto-login token → login with credentials → access protected resource.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestRegistrationFlow:
    """Full registration lifecycle."""

    def test_register_new_user_returns_201_and_token(self, client: TestClient):
        """POST /auth/register → 201 with access_token + user fields."""
        resp = client.post("/auth/register", json={
            "name": "Alice",
            "email": "alice@test.com",
            "password": "securepass123",
            "skills": ["python", "react"],
            "interests": ["AI"],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Alice"
        assert data["email"] == "alice@test.com"
        assert "access_token" in data
        assert data["skills"] == ["python", "react"]
        assert data["interests"] == ["AI"]

    def test_register_duplicate_email_returns_400(self, client: TestClient):
        """Registering the same email twice must fail."""
        payload = {
            "name": "Bob",
            "email": "bob@test.com",
            "password": "pass1234",
        }
        resp1 = client.post("/auth/register", json=payload)
        assert resp1.status_code == 201

        resp2 = client.post("/auth/register", json=payload)
        assert resp2.status_code == 400
        assert "already registered" in resp2.json()["detail"].lower()

    def test_register_missing_fields_returns_422(self, client: TestClient):
        """Missing required fields should trigger validation error."""
        resp = client.post("/auth/register", json={"name": "NoEmail"})
        assert resp.status_code == 422


class TestLoginFlow:
    """Full login lifecycle."""

    def test_login_with_valid_credentials(self, client: TestClient):
        """Register, then login with same credentials → get JWT."""
        # Register first
        client.post("/auth/register", json={
            "name": "Carol",
            "email": "carol@test.com",
            "password": "carolpass",
        })

        # Login
        resp = client.post("/auth/login", json={
            "email": "carol@test.com",
            "password": "carolpass",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password_returns_401(self, client: TestClient):
        """Wrong password must return 401."""
        client.post("/auth/register", json={
            "name": "Dave",
            "email": "dave@test.com",
            "password": "rightpass",
        })

        resp = client.post("/auth/login", json={
            "email": "dave@test.com",
            "password": "wrongpass",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_email_returns_401(self, client: TestClient):
        """Unknown email must return 401."""
        resp = client.post("/auth/login", json={
            "email": "nobody@test.com",
            "password": "anything",
        })
        assert resp.status_code == 401


class TestRegisterThenAccessProtectedResource:
    """Verifies that the JWT from registration works on authenticated endpoints."""

    def test_register_token_grants_access_to_protected_endpoints(self, client: TestClient):
        """
        Full flow: Register → use token → access /profile/me.
        Should return 404 (no profile yet) rather than 401 (unauthorized).
        """
        resp = client.post("/auth/register", json={
            "name": "Eve",
            "email": "eve@test.com",
            "password": "evepass",
        })
        token = resp.json()["access_token"]

        profile_resp = client.get("/profile/me", headers={"Authorization": f"Bearer {token}"})
        # 404 means auth succeeded but no profile exists yet — which is correct
        assert profile_resp.status_code == 404

    def test_no_token_returns_401(self, client: TestClient):
        """Accessing a protected route without a token must return 401."""
        resp = client.get("/profile/me")
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, client: TestClient):
        """A malformed/invalid JWT must return 401."""
        resp = client.get("/profile/me", headers={"Authorization": "Bearer invalid.token.here"})
        assert resp.status_code == 401
