"""Email verification at signup: code issuing, checking, and the register gate."""

import pytest

from app.config import settings
from app.services import otp
from app.services.resume_service import extract_email


class FakeRedis:
    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value, ttl_seconds):
        self.data[key] = value
        return True

    def delete(self, key):
        self.data.pop(key, None)
        return True


@pytest.fixture
def fake_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(otp, "redis_cache", fake)
    return fake


def test_code_round_trip_gives_token_for_that_email_only(fake_redis):
    code = otp.issue_code("Ana@Example.com")
    assert len(code) == 6 and code.isdigit()
    token = otp.check_code("ana@example.com", code)
    assert otp.token_matches_email(token, "ana@example.com")
    assert not otp.token_matches_email(token, "someone@else.com")
    assert not otp.token_matches_email(None, "ana@example.com")
    assert not otp.token_matches_email("garbage", "ana@example.com")


def test_wrong_code_is_rejected_and_attempts_are_limited(fake_redis):
    code = otp.issue_code("a@example.com")
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(otp.MAX_ATTEMPTS):
        with pytest.raises(otp.OTPError):
            otp.check_code("a@example.com", wrong)
    with pytest.raises(otp.OTPError) as exc:
        otp.check_code("a@example.com", code)  # right code, but the budget is spent
    assert exc.value.status_code == 429


def test_code_is_single_use_and_resend_is_throttled(fake_redis):
    code = otp.issue_code("b@example.com")
    with pytest.raises(otp.OTPError) as throttled:
        otp.issue_code("b@example.com")
    assert throttled.value.status_code == 429
    otp.check_code("b@example.com", code)
    with pytest.raises(otp.OTPError):
        otp.check_code("b@example.com", code)


def test_unavailable_store_is_reported(monkeypatch):
    class Down(FakeRedis):
        def set(self, *a, **k):
            return False

    monkeypatch.setattr(otp, "redis_cache", Down())
    with pytest.raises(otp.OTPError) as exc:
        otp.issue_code("c@example.com")
    assert exc.value.status_code == 503


def test_verification_token_cannot_log_in(client, fake_redis):
    token = otp.create_verification_token("d@example.com")
    resp = client.get("/profile/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_register_requires_verification_when_enabled(client, fake_redis, monkeypatch):
    monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", True)
    body = {"name": "E", "email": "e@example.com", "password": "pw-123456"}
    assert client.post("/auth/register", json=body).status_code == 400
    wrong = otp.create_verification_token("other@example.com")
    assert client.post("/auth/register", json={**body, "verification_token": wrong}).status_code == 400
    good = otp.create_verification_token("E@example.com")
    assert client.post("/auth/register", json={**body, "verification_token": good}).status_code == 201


def test_extract_email_prefers_mailto_and_handles_absence():
    assert extract_email("Jane Doe\njane.doe@uni.edu | +91 99999") == "jane.doe@uni.edu"
    text = "Contact: old@x.com\n\nLinks in document:\nmailto:new@y.org"
    assert extract_email(text) == "new@y.org"
    assert extract_email("no address here") == ""
