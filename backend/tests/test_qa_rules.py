import pytest

from app.services.discovery.qa_rules import REJECT_FLAG, classify


@pytest.mark.parametrize("title,category,reason", [
    ("Bridge returned error 0! (20562)", "hackathon", "error-page"),
    ("The Real Python Podcast – Episode #286: Mock Objects", "course", "media-not-posting"),
    ("8 Best Podcasting Courses for Beginners in 2026", "course", "listicle"),
    ("How I Built an AI Agent That Never Forgets", "hackathon", "dev-log"),
    ("Day 4 of Building HYNA-Stage: The Portal is LIVE", "hackathon", "dev-log"),
    ("Building Sentinal: A Multi-Agent AI System", "hackathon", "dev-log"),
    ("js13kGames 2025 winners announced!", "hackathon", "event-over"),
    ("Smart Recipe Application Tutorial with Django", "hackathon", "tutorial"),
    ("Roboflow raises $2.1M for its vision platform", "hackathon", "news-article"),
    ("", "job", "empty-title"),
])
def test_junk_is_rejected_with_a_reason(title, category, reason):
    v = classify(title, "", category)
    assert v.reject and v.reason == reason
    assert v.flags == [REJECT_FLAG, f"qa:{reason}"]


@pytest.mark.parametrize("title,category", [
    ("Essence Journey: Remote Guest Experience Specialist", "job"),
    ("Principal Software Engineer – Customer Journey", "job"),
    ("Zep AI Is Hiring – Building the Agent Context Layer (YC W24)", "job"),
    ("Building REST APIs with Flask", "course"),
    ("Python Tutorial for Beginners (free course)", "course"),
    ("KODA Code Jam Season 3 Hacker Stage is OFFICIALLY OPEN", "hackathon"),
    ("USAII Global AI Hackathon 2026 | Virtual Student Competition", "hackathon"),
    ("A First Step towards Measuring Interdisciplinary Engagement", "research"),
    ("Machine Learning Intern", "internship"),
])
def test_real_postings_are_kept(title, category):
    assert not classify(title, "Register by Dec 1. Prizes.", category).reject


def test_summary_signals_only_apply_to_hackathons_that_are_over():
    assert classify("Hack Night", "Recap of last week's winners announced", "hackathon").reject
    assert not classify("Hack Night", "Winners announced soon. Register now before the deadline.", "hackathon").reject
    assert not classify("Research Fellowship", "winners announced", "research").reject
