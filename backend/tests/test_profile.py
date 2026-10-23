import pytest

from app.schemas.profile import ProfileUpdate


def test_get_profile_404_before_upload(client, auth_headers):
    assert client.get("/profile/me", headers=auth_headers).status_code == 404


def test_patch_profile_404_before_upload(client, auth_headers):
    resp = client.patch("/profile/me", json={"skills": ["Go"]}, headers=auth_headers)
    assert resp.status_code == 404


def test_patch_updates_only_given_fields(client, with_profile):
    resp = client.patch("/profile/me", json={"skills": ["Rust", "Go"]}, headers=with_profile)
    assert resp.status_code == 200
    body = resp.json()
    assert body["skills"] == ["Rust", "Go"]
    assert body["interests"] == ["ML"]  # untouched


def test_patch_cleans_and_dedupes(client, with_profile):
    resp = client.patch(
        "/profile/me",
        json={"interests": ["  Machine   Learning ", "machine learning", "", "Web3"]},
        headers=with_profile,
    )
    assert resp.json()["interests"] == ["Machine Learning", "Web3"]


def test_patch_invalidates_cached_profile(client, with_profile):
    first = client.get("/profile/me", headers=with_profile).json()
    assert client.get("/profile/me", headers=with_profile).json()["from_cache"] is True

    client.patch("/profile/me", json={"skills": ["Kotlin"]}, headers=with_profile)
    after = client.get("/profile/me", headers=with_profile).json()
    assert first["skills"] == ["Python", "SQL"]
    assert after["skills"] == ["Kotlin"]
    assert after["from_cache"] is False


def test_profile_update_schema_limits():
    with pytest.raises(ValueError):
        ProfileUpdate(skills=["x"] * 101)
    assert ProfileUpdate(skills=["a" * 100]).skills == ["a" * 60]
