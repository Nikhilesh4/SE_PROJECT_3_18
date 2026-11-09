from datetime import datetime, timezone

from app.services.insights import signals
from app.services.insights.ics import build_ics
from app.services.missions import parse_query


def test_stipend_extraction_normalises_to_inr_per_month():
    assert signals.extract_stipend("Stipend: ₹25,000/month")["amount"] == 25000
    assert signals.extract_stipend("Paid $2k per month")["amount"] == 2000 * 83
    assert round(signals.extract_stipend("Rs. 8 lakhs per annum")["amount"]) == 66667
    assert signals.extract_stipend("pay $5 for the ticket") is None
    assert signals.extract_stipend("no money mentioned") is None


def test_scam_detector_flags_fees_and_chat_only_contact():
    risky = signals.assess_scam_risk("Data entry", "Pay a registration fee of 500. Contact on WhatsApp only")
    assert risky.risky and "asks-for-fee" in risky.flags
    clean = signals.assess_scam_risk("Backend intern", "Build APIs with Python. Apply on our careers page.")
    assert not clean.risky and clean.score == 0


def test_eligibility_parsing_and_checking():
    rules = signals.parse_eligibility("Open to batch of 2026, 2027. Minimum CGPA 7.5. CSE or ECE students.")
    assert rules.years == [2026, 2027] and rules.min_cgpa == 7.5 and "cse" in rules.branches
    problems = signals.check_eligibility(rules, grad_year=2025, cgpa=7.0)
    assert len(problems) == 2
    assert signals.check_eligibility(rules, grad_year=2026, cgpa=8.0) == []


def test_remote_and_skill_detection():
    assert signals.detect_remote("Dev", "Fully remote role")
    assert not signals.detect_remote("Dev", "On-site only in Pune")
    assert signals.extract_skills("Python, C++ and Next.js; nor cargo") == ["python", "c++", "next.js"]


def test_ics_has_event_and_alarm():
    from app.models.rss_item import RssItem
    item = RssItem(id=7, title="Apply; now, please", url="https://x.io/a", source_name="S",
                   application_deadline=datetime(2026, 12, 1, 9, 0, tzinfo=timezone.utc))
    ics = build_ics([item, RssItem(id=8, title="no deadline", url="u", source_name="S")])
    assert ics.count("BEGIN:VEVENT") == 1 and "TRIGGER:-P3D" in ics
    assert "DTSTART:20261201T090000Z" in ics and "Apply\\; now\\, please" in ics
    assert "\r\n" in ics


def test_mission_query_parsing():
    p = parse_query("remote paid ML internships, at least ₹20k/month, deadline after Dec",
                    today=datetime(2026, 11, 9, tzinfo=timezone.utc))
    assert p["category"] == "internship" and p["remote_only"] and p["min_stipend"] == 20000
    assert p["deadline_after"] == datetime(2026, 12, 1, tzinfo=timezone.utc)
    assert "ml" in p["keywords"]
