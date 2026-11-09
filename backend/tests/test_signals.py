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


def test_stipend_period_inference_and_parsing_edge_cases():
    amount = lambda t: round(signals.extract_stipend(t)["amount"])
    assert amount("$120k") == round(120_000 * 83 / 12)          # a big bare number is a yearly salary
    assert amount("£70,000 K") == round(70_000 * 105 / 12)      # "K" after a full number is not a x1000 multiplier
    assert amount("Stipend ₹ 50000") == 50000                   # unformatted numbers are read whole
    assert amount("₹25,000") == 25000                           # a smaller INR amount is a monthly stipend
    assert amount("₹3,60,000") == 30000                         # a big INR amount is yearly
    assert amount("$6/hour") == round(6 * 160 * 83)
    assert signals.extract_stipend("Win a $100 prize") is None  # bare amounts under 1,000 are not stipends
    assert signals.extract_stipend("tickets $500") is None


def test_summarize_amounts_gives_quartiles_and_handles_small_samples():
    s = signals.summarize_amounts([10_000, 20_000, 30_000, 40_000, 50_000])
    assert (s["count"], s["p25"], s["median"], s["p75"], s["min"], s["max"]) == (5, 20_000, 30_000, 40_000, 10_000, 50_000)
    assert signals.summarize_amounts([5_000, 9_000])["median"] == 7_000
    assert signals.summarize_amounts([]) is None
    assert signals.stipend_in_range(25_000) and not signals.stipend_in_range(500) and not signals.stipend_in_range(9e8)


def test_stipend_insights_endpoint_uses_clean_pay_data(client, seed_items):
    from datetime import timedelta
    from tests.conftest import make_item

    seed_items(
        make_item(url="https://e.com/s1", title="Python Intern", summary="Stipend ₹20,000/month. Python and SQL.", category="internship"),
        make_item(url="https://e.com/s2", title="Python Intern II", summary="Stipend ₹30,000/month. Python.", category="internship"),
        make_item(url="https://e.com/s3", title="Python Intern III", summary="Stipend ₹40,000/month. Python. Remote.", category="internship"),
        make_item(url="https://e.com/j1", title="Senior Engineer", summary="Salary $120k. Go.", category="job"),
        make_item(url="https://e.com/h1", title="Hack It", summary="Win a $5,000 prize. Register now.", category="hackathon"),
        make_item(url="https://e.com/n1", title="No pay stated", summary="Great team.", category="internship"),
        make_item(url="https://e.com/x1", title="Odd", summary="Pays $1,000,000,000/year", category="job"),
    )
    d = client.get("/api/insights/stipends").json()
    assert d["unit"] == "INR per month" and d["with_pay"] == 4 and d["postings"] == 7
    assert d["by_category"]["internship"]["median"] == 30_000 and d["by_category"]["internship"]["count"] == 3
    assert d["by_category"]["job"]["median"] == round(120_000 * 83 / 12)      # annual salary, not monthly
    assert "hackathon" not in d["by_category"] and d["left_out"]["not_pay_category"] == 1  # prizes are not pay
    assert d["left_out"]["out_of_range"] == 1
    assert d["by_skill"][0]["skill"] == "python" and d["by_skill"][0]["count"] == 3
    assert 0 < d["coverage"] < 1

    only = client.get("/api/insights/stipends", params={"category": "internship"}).json()
    assert list(only["by_category"]) == ["internship"] and only["overall"]["count"] == 3


def test_trends_stipends_no_longer_count_prizes_or_outliers(client, seed_items):
    from tests.conftest import make_item

    seed_items(
        make_item(url="https://e.com/t1", title="Hack", summary="$10,000 prize pool. Register.", category="hackathon"),
        make_item(url="https://e.com/t2", title="Intern", summary="₹25,000/month stipend", category="internship"),
    )
    t = client.get("/api/insights/trends").json()["stipend_inr_month"]
    assert list(t) == ["internship"] and t["internship"]["median"] == 25_000 and "p25" in t["internship"]
