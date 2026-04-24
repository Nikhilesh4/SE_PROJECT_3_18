"""
E2E Tests — Health & Root Endpoints
=====================================
Basic smoke tests to verify the API is running.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestRootEndpoint:
    """GET / — API root."""

    def test_root_returns_200(self, client: TestClient):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data
        assert "running" in data["message"].lower()


class TestHealthEndpoint:
    """GET /health — health check."""

    def test_health_returns_healthy(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
