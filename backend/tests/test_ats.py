from types import SimpleNamespace

from app.services import ats

GOOD = """Jane Doe
jane@example.com | +91 98765 43210 | github.com/jane | linkedin.com/in/jane

SKILLS
Python, SQL, Docker

EXPERIENCE
• Built a Python service handling 10k requests per day.
• Reduced query latency by 40% using SQL indexes.
• Deployed Docker images to production with CI.
• Designed a REST API used by 3 teams.
• Automated reports, saving 5 hours a week.

PROJECTS
• Created a recommender in Python with 85% accuracy.

EDUCATION
B.Tech Computer Science, 2026
""" + "Filler words for length. " * 30


def profile(text, skills=()):
    return SimpleNamespace(raw_text=text, parsed_skills=list(skills), parsed_interests=[])


def item(title="Python Backend Intern", summary="Work with Python, Kubernetes and SQL.", tags=()):
    return SimpleNamespace(id=7, title=title, summary=summary, tags=list(tags))


def test_no_resume_text_is_reported_not_scored():
    assert ats.check_resume(profile(""))["has_resume"] is False
    assert ats.check_resume(None)["has_resume"] is False


def test_well_formed_resume_scores_high_without_posting():
    out = ats.check_resume(profile(GOOD))
    assert out["format_score"] >= 90 and out["suggestions"] == []


def test_bad_format_produces_fixes():
    out = ats.check_resume(profile("Jane | Doe | python | sql | " * 40))
    fixes = " ".join(out["suggestions"])
    assert out["format_score"] < 50
    assert "Experience" in fixes and "email" in fixes.lower() and "layout" in fixes.lower()


def test_keyword_gap_is_split_between_unstated_and_truly_missing():
    out = ats.check_resume(profile(GOOD, skills=["Python", "Kubernetes"]), item())
    kw = out["keywords"]
    assert {"python", "sql"} <= {k.lower() for k in kw["matched"]}
    assert kw["listed_in_profile_but_not_in_resume_text"] == ["kubernetes"]
    assert kw["missing"] == ["kubernetes"]
    assert not any("only if you genuinely have" in s for s in out["suggestions"])  # kubernetes is in the profile
    assert any("never states it plainly" in s for s in out["suggestions"])


def test_missing_skill_not_in_profile_warns_not_to_fabricate():
    out = ats.check_resume(profile(GOOD, skills=["Python"]), item())
    assert any("only if you genuinely have" in s for s in out["suggestions"])

