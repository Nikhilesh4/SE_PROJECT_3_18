from tests.conftest import register


def test_register_returns_token_and_user(client):
    resp = client.post(
        "/auth/register",
        json={"name": "Ana", "email": "ana@example.com", "password": "pw-123456"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "ana@example.com"
    assert body["access_token"]


def test_register_rejects_duplicate_email(client):
    register(client, "dup@example.com")
    resp = client.post(
        "/auth/register",
        json={"name": "Again", "email": "dup@example.com", "password": "pw-123456"},
    )
    assert resp.status_code == 400


def test_login_success_and_wrong_password(client):
    register(client, "login@example.com")
    ok = client.post("/auth/login", json={"email": "login@example.com", "password": "s3cret-pass"})
    assert ok.status_code == 200
    assert ok.json()["token_type"] == "bearer"

    bad = client.post("/auth/login", json={"email": "login@example.com", "password": "nope"})
    assert bad.status_code == 401


def test_protected_route_requires_token(client):
    assert client.get("/api/bookmarks").status_code == 401
    bad = client.get("/api/bookmarks", headers={"Authorization": "Bearer not-a-jwt"})
    assert bad.status_code == 401
