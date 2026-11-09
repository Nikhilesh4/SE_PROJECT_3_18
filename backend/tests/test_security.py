"""G9 security basics: JWT secret validation and rate limiting."""

import pytest

from app.config import MIN_SECRET_KEY_LENGTH, resolve_secret_key, settings
from app.rate_limit import limiter
from tests.conftest import register

GOOD_KEY = "k" * MIN_SECRET_KEY_LENGTH


# ── SECRET_KEY ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "value",
    ["change-me", "change-me-in-production", "your-super-secret-key-change-this-in-production", "Secret"],
)
def test_placeholder_secret_is_refused(value, tmp_path):
    with pytest.raises(RuntimeError, match="placeholder"):
        resolve_secret_key(value, tmp_path / "key")


def test_short_secret_is_refused(tmp_path):
    with pytest.raises(RuntimeError, match="at least"):
        resolve_secret_key("too-short", tmp_path / "key")


def test_explicit_secret_is_used_as_is(tmp_path):
    key_file = tmp_path / "key"
    assert resolve_secret_key(GOOD_KEY, key_file) == GOOD_KEY
    assert not key_file.exists()


def test_missing_secret_is_generated_once_and_reused(tmp_path):
    key_file = tmp_path / "key"
    first = resolve_secret_key(None, key_file)
    assert len(first) >= MIN_SECRET_KEY_LENGTH
    assert first not in {"change-me", "change-me-in-production"}
    assert key_file.read_text() == first
    assert key_file.stat().st_mode & 0o077 == 0  # owner-only
    assert resolve_secret_key("", key_file) == first


def test_unwritable_key_file_falls_back_to_a_temporary_key(tmp_path):
    key_file = tmp_path / "no-such-dir" / "key"
    a, b = resolve_secret_key(None, key_file), resolve_secret_key(None, key_file)
    assert len(a) >= MIN_SECRET_KEY_LENGTH and a != b


# ── Rate limiting ────────────────────────────────────────────────────────────

@pytest.fixture
def limits(monkeypatch):
    """Turn the limiter on with small limits; restore it afterwards."""
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT", "3/minute")
    monkeypatch.setattr(settings, "REGISTER_RATE_LIMIT", "100/minute")
    monkeypatch.setattr(settings, "UPLOAD_RATE_LIMIT", "2/minute")
    limiter.enabled = True
    limiter.reset()
    yield
    limiter.enabled = False
    limiter.reset()


def _login(client, password="wrong-password"):
    return client.post("/auth/login", json={"email": "student@example.com", "password": password})


def test_login_is_rate_limited(client, limits):
    register(client)
    assert [_login(client).status_code for _ in range(3)] == [401, 401, 401]
    blocked = _login(client)
    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"] == "60"
    assert "Too many requests" in blocked.json()["detail"]
    # Even the right password is refused while the limit holds.
    assert _login(client, "s3cret-pass").status_code == 429


def test_register_is_rate_limited(client, limits, monkeypatch):
    monkeypatch.setattr(settings, "REGISTER_RATE_LIMIT", "2/minute")
    limiter.reset()
    codes = [
        client.post(
            "/auth/register",
            json={"name": "S", "email": f"s{i}@example.com", "password": "s3cret-pass"},
        ).status_code
        for i in range(3)
    ]
    assert codes == [201, 201, 429]


def test_upload_limit_is_per_user(client, limits):
    alice = register(client, "alice@example.com")
    bob = register(client, "bob@example.com")

    def upload(headers):
        return client.post(
            "/profile/upload-resume",
            headers=headers,
            files={"file": ("cv.txt", b"not a pdf", "text/plain")},
        ).status_code

    assert [upload(alice), upload(alice)] == [400, 400]  # rejected by validation, still counted
    assert upload(alice) == 429
    assert upload(bob) == 400  # same IP, different user: unaffected


def test_limits_do_nothing_when_disabled(client):
    register(client)
    assert {_login(client).status_code for _ in range(15)} == {401}
