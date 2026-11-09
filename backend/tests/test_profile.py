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


def test_manual_profile_is_created_without_a_resume(client, auth_headers):
    body = {
        "name": "  Asha   Rao ",
        "skills": ["Python", "python", " Go "],
        "interests": ["ML"],
        "education": [{"degree": "BTech", "institution": "IIIT", "year": "2026"}, {"degree": "", "institution": "", "year": ""}],
        "experience": [{"role": "Intern", "company": "Acme", "duration": "2025", "summary": "Built things"}],
        "socials": [{"label": "GitHub", "url": "https://github.com/asha"}, {"label": "", "url": ""}],
    }
    resp = client.put("/profile/me", json=body, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Asha Rao"
    assert data["skills"] == ["Python", "Go"]
    assert len(data["education"]) == 1 and len(data["socials"]) == 1
    assert client.get("/profile/me", headers=auth_headers).json()["experience"][0]["company"] == "Acme"


def test_manual_profile_replaces_existing_one(client, with_profile):
    resp = client.put("/profile/me", json={"skills": ["Rust"]}, headers=with_profile)
    assert resp.status_code == 200
    assert resp.json()["skills"] == ["Rust"]
