import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.db import SessionLocal
from app.models.activity import AgentRun
from app.models.rss_item import RssItem
from app.schemas.rss_item import NormalizedRssItem
from app.services import llm
from app.services.adapters.base_adapter import OpportunityAdapter
from app.services.discovery import fetcher, pipeline, scholarly, websearch
from app.services.discovery.ats import ATSAdapter, parse_ashby, parse_greenhouse, parse_lever, parse_smartrecruiters, parse_workable
from app.services.discovery.devpost import DevpostAdapter, parse_hackathons
from app.services.discovery.hn import HNHiringAdapter, parse_comment
from app.services.discovery.programs import ProgramsAdapter
from app.services.discovery.textutil import html_to_text, parse_date_range_end
from tests.conftest import make_item

NOW = datetime.now(timezone.utc)


# ── text helpers ─────────────────────────────────────────────────────────────

def test_html_to_text_handles_escaped_html_and_scripts():
    assert html_to_text("&lt;p&gt;Hello &amp;amp; welcome&lt;/p&gt;&lt;h2&gt;Role&lt;/h2&gt;") == "Hello & welcome\nRole"
    assert html_to_text("<script>x()</script><p>Keep<br>this</p>") == "Keep\nthis"


def test_date_range_end():
    assert parse_date_range_end("Oct 01 - Nov 12, 2026") == datetime(2026, 11, 12, 23, 59, tzinfo=timezone.utc)
    assert parse_date_range_end("nonsense") is None


# ── ATS vendors ──────────────────────────────────────────────────────────────

GH = {"jobs": [
    {"id": 1, "title": "Software Engineer Intern", "absolute_url": "https://x.com/1", "company_name": "Acme", "first_published": "2026-10-01T10:00:00-04:00",
     "location": {"name": "Remote"}, "content": "&lt;p&gt;Build things with Python&lt;/p&gt;", "departments": [{"name": "Eng"}]},
    {"id": 2, "title": "Senior Staff Engineer", "absolute_url": "https://x.com/2", "company_name": "Acme", "location": {"name": "NYC"}, "content": "", "departments": []},
]}
LEVER = [{"id": "a-1", "text": "New Grad Engineer", "hostedUrl": "https://jobs.lever.co/p/a-1", "createdAt": 1786469891368,
          "categories": {"location": "London", "team": "Eng", "commitment": "Full-time"}, "descriptionPlain": "Work on data", "workplaceType": "remote"}]
ASHBY = {"jobs": [{"id": "z", "title": "Junior Backend Engineer", "jobUrl": "https://jobs.ashbyhq.com/r/z", "location": "NYC", "isRemote": True, "isListed": True,
                   "descriptionPlain": "APIs", "publishedAt": "2026-04-07T17:12:35.753+00:00", "compensation": {"compensationTierSummary": "$100K"}},
                  {"id": "h", "title": "Hidden Intern", "jobUrl": "https://jobs.ashbyhq.com/r/h", "isListed": False}]}
WORKABLE = {"name": "Wk", "jobs": [{"title": "Data Intern", "shortcode": "ABC", "url": "https://apply.workable.com/wk/j/ABC", "city": "Berlin", "country": "Germany", "description": "<p>Data</p>", "created_at": "2026-10-10"}]}
SR = {"content": [{"id": "9", "name": "Graduate Analyst", "releasedDate": "2026-10-01T00:00:00Z", "location": {"city": "Pune", "country": "in", "remote": False},
                   "company": {"name": "Visa"}, "department": {"label": "Risk"}, "typeOfEmployment": {"label": "Full-time"}}]}


def test_vendor_parsers_normalise_fields():
    gh = parse_greenhouse(GH, "acme", "Acme")
    assert gh[0].title == "Software Engineer Intern — Acme (Remote)" and gh[0].category == "internship"
    assert gh[0].discovered_by == "ats:greenhouse" and gh[0].confidence == 0.95 and "Build things with Python" in gh[0].summary
    assert gh[0].guid == "ats:greenhouse:1"

    lv = parse_lever(LEVER, "p", "Palantir")[0]
    assert lv.url.endswith("a-1") and lv.published_at.year == 2026 and "remote" in lv.summary.lower()

    ab = parse_ashby(ASHBY, "r", "Ramp")
    assert len(ab) == 1 and "Compensation: $100K" in ab[0].summary and ab[0].summary.startswith("Compensation") or "Remote" in ab[0].summary

    wk = parse_workable(WORKABLE, "wk", "Wk")[0]
    assert wk.category == "internship" and "Berlin" in wk.title
    sr = parse_smartrecruiters(SR, "Visa", "Visa")[0]
    assert sr.url == "https://jobs.smartrecruiters.com/Visa/9" and "Pune" in sr.title


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_ats_adapter_keeps_early_career_and_isolates_failures():
    def handler(req: httpx.Request):
        if "greenhouse" in req.url.host:
            return httpx.Response(200, json=GH)
        if "lever" in req.url.host:
            return httpx.Response(500)
        return httpx.Response(200, json=ASHBY)

    adapter = ATSAdapter(
        [{"vendor": "greenhouse", "token": "acme", "name": "Acme"}, {"vendor": "lever", "token": "bad"}, {"vendor": "ashby", "token": "r", "name": "Ramp"}],
        client=_client(handler))
    titles = [i.title for i in adapter.fetch_opportunities()]
    assert any("Software Engineer Intern" in t for t in titles) and any("Junior Backend" in t for t in titles)
    assert not any("Senior Staff" in t for t in titles)

    everything = ATSAdapter([{"vendor": "greenhouse", "token": "acme"}], early_career_only=False, client=_client(handler)).fetch_opportunities()
    assert len(everything) == 2


def test_shipped_watchlist_loads():
    from app.services.discovery.ats import load_watchlist
    assert {e["vendor"] for e in load_watchlist()} <= {"greenhouse", "lever", "ashby", "workable", "smartrecruiters"}


# ── HN ───────────────────────────────────────────────────────────────────────

def test_hn_comment_parsing():
    c = {"id": 5, "author": "u", "created_at": "2026-11-02T16:00:00Z",
         "text": "Acme | Software Engineering Intern | Remote (US) | $30/hr<p>We build robots. Apply: https:&#x2F;&#x2F;acme.io&#x2F;jobs"}
    item = parse_comment(c)
    assert item.title == "Software Engineering Intern — Acme (Remote (US))" and item.category == "internship"
    assert item.url == "https://news.ycombinator.com/item?id=5" and "Apply: https://acme.io/jobs" in item.summary
    assert parse_comment({"id": 6, "author": "u", "text": "Just chatting, no format here"}) is None
    assert parse_comment({"id": 7, "author": None, "text": None}) is None


def test_hn_adapter_end_to_end_with_mock():
    def handler(req: httpx.Request):
        if "search_by_date" in req.url.path:
            return httpx.Response(200, json={"hits": [{"objectID": "1", "title": "Ask HN: Who wants to be hired?"}, {"objectID": "2", "title": "Ask HN: Who is hiring? (November 2026)"}]})
        assert req.url.path.endswith("/items/2")
        return httpx.Response(200, json={"children": [
            {"id": 10, "author": "a", "text": "Acme | Intern | Remote<p>Python"},
            {"id": 11, "author": "b", "text": "Big | Staff Engineer | NYC<p>Ten years experience"},
        ]})
    items = HNHiringAdapter(client=_client(handler)).fetch_opportunities()
    assert [i.guid for i in items] == ["hn:10"]


# ── Devpost / programs / scholarly ───────────────────────────────────────────

DEVPOST = {"hackathons": [{"id": 1, "title": "AI Hack", "url": "https://aihack.devpost.com/?utm=x", "displayed_location": {"location": "Online"},
                           "submission_period_dates": "Oct 01 - Nov 12, 2026", "themes": [{"name": "Machine Learning/AI"}],
                           "prize_amount": "$<span>67,500</span>", "organization_name": "PayPal", "time_left_to_submission": "3 days left"}]}


def test_devpost_parsing():
    (h,) = parse_hackathons(DEVPOST)
    assert h.url == "https://aihack.devpost.com/" and h.category == "hackathon" and "$67,500" in h.summary
    assert h.application_deadline.month == 11
    items = DevpostAdapter(client=_client(lambda r: httpx.Response(200, json=DEVPOST)), pages=1).fetch_opportunities()
    assert len(items) == 1


def test_programs_catalogue():
    items = ProgramsAdapter().fetch_opportunities()
    assert any("Google Summer of Code" in i.title for i in items) and all(i.application_deadline is None for i in items)


ARXIV = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/1</id><published>2026-10-01T00:00:00Z</published>
<title>Fast  Transformers</title><summary>We make things fast.</summary><author><name>Ada Lovelace</name></author><author><name>Alan Turing</name></author></entry></feed>"""
S2 = {"data": [{"paperId": "p", "title": "Efficient Attention", "year": 2026, "abstract": "x", "authors": [
    {"name": "Ada Lovelace", "authorId": "1", "affiliations": ["MIT"], "homepage": "https://ada.mit.edu"}]}]}


def test_scholarly_scout_ranks_authors_and_survives_partial_failure():
    def handler(req: httpx.Request):
        if "arxiv" in req.url.host:
            return httpx.Response(200, text=ARXIV)
        return httpx.Response(200, json=S2)
    out = scholarly.scout("attention", client=_client(handler))
    assert out["errors"] == [] and out["contacts"][0]["name"] == "Ada Lovelace"
    assert out["contacts"][0]["affiliations"] == ["MIT"] and len(out["contacts"][0]["papers"]) == 2

    out = scholarly.scout("attention", client=_client(lambda r: httpx.Response(429) if "semantic" in r.url.host else httpx.Response(200, text=ARXIV)))
    assert out["papers"] and out["errors"] and "semantic_scholar" in out["errors"][0]

    mail = scholarly.template_cold_email(student_name="Sam", topic="attention", person="Ada Lovelace", paper="Fast Transformers", skills=["PyTorch"])
    assert "Professor Lovelace" in mail["body"] and "PyTorch" in mail["body"]


# ── fetcher guardrails ───────────────────────────────────────────────────────

@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.com/x", "http://127.0.0.1:8000/admin", "http://localhost/x",
                                 "http://169.254.169.254/latest/meta-data", "http://10.0.0.5/", "https://user:pw@example.com/", "http://[::1]/"])
def test_fetcher_blocks_unsafe_urls(url):
    with pytest.raises(fetcher.FetchBlocked):
        fetcher.check_url(url)


def test_fetcher_allowlist_and_public_ip(monkeypatch):
    assert fetcher.check_url("http://8.8.8.8/x") == "http://8.8.8.8/x"
    monkeypatch.setattr(fetcher.settings, "FETCH_ALLOWED_DOMAINS", "acme.io")
    with pytest.raises(fetcher.FetchBlocked):
        fetcher.check_url("http://8.8.8.8/x")


def test_fetch_page_respects_robots_and_revalidates_redirects(monkeypatch):
    monkeypatch.setattr(fetcher, "_robots", {})
    monkeypatch.setattr(fetcher, "HOST_DELAY_SECONDS", 0)

    def handler(req: httpx.Request):
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private")
        if req.url.path == "/jump":
            return httpx.Response(302, headers={"location": "http://127.0.0.1/secret"})
        return httpx.Response(200, text="<html>ok</html>", headers={"content-type": "text/html"})

    c = httpx.Client(transport=httpx.MockTransport(handler))
    assert fetcher.fetch_page("http://8.8.8.8/open", client=c).text == "<html>ok</html>"
    with pytest.raises(fetcher.FetchBlocked, match="robots"):
        fetcher.fetch_page("http://8.8.8.8/private/x", client=c)
    with pytest.raises(fetcher.FetchBlocked, match="non-public"):
        fetcher.fetch_page("http://8.8.8.8/jump", client=c)


# ── web search agent ─────────────────────────────────────────────────────────

LD_PAGE = """<html><script type="application/ld+json">{"@type":"JobPosting","title":"ML Research Intern","hiringOrganization":{"name":"Lab Inc"},
"jobLocation":{"address":{"addressLocality":"Pune","addressCountry":"IN"}},"validThrough":"2026-12-31","description":"<p>Work on models</p>"}</script></html>"""


def test_extract_posting_prefers_json_ld():
    item = websearch.extract_posting("https://lab.io/j/1", LD_PAGE, use_llm=False)
    assert item.title == "ML Research Intern — Lab Inc (Pune, IN)" and item.application_deadline.year == 2026
    assert item.discovered_by == "web_search" and item.confidence == 0.7


def test_extract_posting_llm_and_heuristic(monkeypatch):
    monkeypatch.setattr(llm, "complete_sync", lambda system, prompt: '{"is_posting": true, "title": "Data Intern", "company": "Foo", "location": "", "category": "internship", "deadline": null, "summary": "Data work"}')
    assert websearch.extract_posting("https://foo.io/x", "<p>some page</p>").title == "Data Intern — Foo"
    monkeypatch.setattr(llm, "complete_sync", lambda system, prompt: '{"is_posting": false}')
    assert websearch.extract_posting("https://foo.io/x", "<p>blog</p>") is None
    monkeypatch.setattr(llm, "complete_sync", lambda *a: None)
    body = "<p>" + "Responsibilities include building APIs. Requirements: Python. Apply today. " * 8 + "</p>"
    assert websearch.extract_posting("https://foo.io/x", body, snippet_title="Backend Intern at Foo").category == "internship"
    assert websearch.extract_posting("https://foo.io/x", "<p>short</p>", snippet_title="Backend Intern") is None


def test_plan_queries_fallback_and_llm(monkeypatch):
    monkeypatch.setattr(llm, "complete_sync", lambda *a: None)
    qs = websearch.plan_queries(["python", "sql"], ["machine learning"])
    assert 1 <= len(qs) <= 3 and all("machine learning" in q or "python" in q for q in qs)
    monkeypatch.setattr(llm, "complete_sync", lambda *a: 'Sure: ["ml intern india", "nlp research internship"]')
    assert websearch.plan_queries(["python"], ["ml"]) == ["ml intern india", "nlp research internship"]
    assert websearch.plan_queries([], []) == []


def test_web_discovery_is_budgeted_and_skips_blocked(monkeypatch):
    monkeypatch.setattr(websearch.settings, "TAVILY_API_KEY", "k")
    monkeypatch.setattr(llm, "complete_sync", lambda *a: None)
    monkeypatch.setattr(websearch, "search", lambda q, **kw: [{"title": "T", "url": f"https://site{i}.io/{q[:3]}", "snippet": ""} for i in range(5)])
    fetched = []

    def fake_fetch(url, **kw):
        fetched.append(url)
        if "site0" in url:
            raise fetcher.FetchBlocked("nope")
        return fetcher.Page(url, 200, LD_PAGE, "text/html")
    monkeypatch.setattr(fetcher, "fetch_page", fake_fetch)
    items = websearch.discover_for_profile(["python"], ["ml"], max_pages=4)
    assert len(fetched) == 4 and 0 < len(items) <= 3


# ── pipeline ─────────────────────────────────────────────────────────────────

class Fake(OpportunityAdapter):
    def __init__(self, items): self.items, self.calls = items, 0
    def fetch_opportunities(self, **_):
        self.calls += 1
        return self.items


def _item(**kw):
    base = dict(title="Python Intern — Acme", url="https://acme.io/1", summary="Great internship. Apply now with Python.", category="internship",
                source_name="Acme", feed_url="x", discovered_by="ats:greenhouse", confidence=0.95, guid="ats:greenhouse:1", author="Acme")
    base.update(kw)
    return NormalizedRssItem(**base)


def test_verify_rules():
    assert not pipeline.verify(_item(application_deadline=NOW - timedelta(days=1))).keep
    scam = pipeline.verify(_item(summary="Pay a registration fee. WhatsApp only. Bank account number needed."))
    assert not scam.keep and "scam-risk" in scam.flags
    soft = pipeline.verify(_item(summary="Contact us on WhatsApp only. Apply now."))
    assert soft.keep and "scam-risk" not in soft.flags or soft.confidence <= 0.2
    assert not pipeline.verify(_item(), link_checker=lambda u: False).keep
    ok = pipeline.verify(_item(), link_checker=lambda u: True)
    assert ok.keep and ok.confidence == 1.0
    assert "link-unchecked" in pipeline.verify(_item(), link_checker=lambda u: None).flags


def test_dedupe_keeps_higher_confidence_copy():
    a = _item(confidence=0.5, url="https://a.io/x", discovered_by="web_search", guid="w1")
    b = _item(confidence=0.95, url="https://b.io/y")  # same title+company
    out, dropped = pipeline.dedupe([a, b])
    assert dropped == 1 and [i.confidence for i in out] == [0.95]


def test_run_discovery_end_to_end_with_trace_and_throttle(db):
    good = _item()
    expired = _item(title="Old Role", url="https://acme.io/old", guid="ats:greenhouse:2", author="Acme", application_deadline=NOW - timedelta(days=3))
    scam = _item(title="Data entry", url="https://acme.io/scam", guid="ats:greenhouse:3", author="X", summary="Registration fee required. Bank account number. WhatsApp only. Apply now")
    fake = Fake([good, expired, scam])

    session = SessionLocal()
    try:
        out = pipeline.run_discovery(session, {"ats": fake}, enrich_fetch=lambda url: "<p>" + "Full description with lots of details about the role. " * 12 + "</p>")
        assert out["found"] == 3 and out["kept"] == 1 and out["upserted"] == 1 and out["enriched"] == 1
        row = session.query(RssItem).one()
        assert row.discovered_by == "ats:greenhouse" and row.confidence == 0.95 and row.verified_at is not None and len(row.summary) > 400

        run = session.get(AgentRun, out["run_id"])
        stages = [s["stage"] for s in run.steps]
        assert stages == ["plan", "source", "extract", "verify", "persist", "enrich", "qa"] and run.status == "ok"
        verify_step = next(s for s in run.steps if s["stage"] == "verify")
        assert "deadline already passed" in verify_step["dropped"]

        # Second run is throttled: the source ran moments ago.
        again = pipeline.run_discovery(session, {"ats": fake})
        assert fake.calls == 1 and again["found"] == 0
        forced = pipeline.run_discovery(session, {"ats": fake}, force=True)
        assert fake.calls == 2 and forced["found"] == 3
    finally:
        session.close()


def test_pipeline_survives_source_failure(db):
    class Boom(OpportunityAdapter):
        def fetch_opportunities(self, **_): raise RuntimeError("api down")
    session = SessionLocal()
    try:
        out = pipeline.run_discovery(session, {"a": Boom(), "b": Fake([_item()])}, force=True)
        assert out["kept"] == 1
        run = session.get(AgentRun, out["run_id"])
        assert any(s["stage"] == "source_error" for s in run.steps)
    finally:
        session.close()


def test_ingestion_qa_flags_articles_and_hides_them(client, seed_items):
    article, real = seed_items(
        make_item(url="https://e.com/a", title="Top 10 ways to land an internship", summary="Tips and tricks for students.", category="internship"),
        make_item(url="https://e.com/r", title="Python Developer Intern", summary="We are hiring. Apply now."),
    )
    session = SessionLocal()
    try:
        res = pipeline.ingestion_qa(session)
        assert res["flagged"] >= 1 and pipeline.ingestion_qa(session)["checked"] == 0
        assert "not-opportunity" in session.get(RssItem, article.id).flags
        assert "not-opportunity" not in session.get(RssItem, real.id).flags
    finally:
        session.close()
    ids = [i["id"] for i in client.get("/api/feeds/rss").json()["items"]]
    assert real.id in ids and article.id not in ids


def test_qa_records_reasons_and_rechecks_when_rules_version_changes(client, seed_items):
    podcast, real = seed_items(
        make_item(url="https://e.com/p", title="The Real Python Podcast – Episode #300: Testing", summary="Listen now.", category="course"),
        make_item(url="https://e.com/c", title="Building REST APIs with Flask", summary="Enroll in this course.", category="course"),
    )
    session = SessionLocal()
    try:
        res = pipeline.ingestion_qa(session)
        assert res["reasons"].get("media-not-posting") == 1
        assert {"not-opportunity", "qa:media-not-posting"} <= set(session.get(RssItem, podcast.id).flags)
        assert "qa:media-not-posting" not in session.get(RssItem, real.id).flags

        # A row stamped with an older rules version is checked again.
        row = session.get(RssItem, real.id)
        row.flags = ["qa-v1"]
        session.commit()
        assert pipeline.ingestion_qa(session)["checked"] == 1
        assert pipeline.ingestion_qa(session)["checked"] == 0
    finally:
        session.close()


def test_flagged_postings_are_hidden_from_search_but_not_from_direct_lookup(client, seed_items, auth_headers):
    junk, real = seed_items(
        make_item(url="https://e.com/j", title="How I built a hackathon app with Django", summary="Hackathon write-up, register link inside.", category="hackathon"),
        make_item(url="https://e.com/g", title="Hackathon Django Challenge", summary="Register by Dec 1. Prizes.", category="hackathon"),
    )
    session = SessionLocal()
    try:
        pipeline.ingestion_qa(session)
    finally:
        session.close()
    ids = [i["id"] for i in client.get("/api/search", params={"q": "hackathon django"}, headers=auth_headers).json()["items"]]
    assert real.id in ids and junk.id not in ids
    assert client.get(f"/api/feeds/items/{junk.id}").status_code == 200  # still reachable by id; the flag is reversible


def test_qa_does_not_hide_real_postings_just_because_the_summary_is_thin(client, seed_items):
    (job,) = seed_items(make_item(url="https://e.com/bj", title="Backend Java Developer", summary="", category="job"))
    session = SessionLocal()
    try:
        assert pipeline.ingestion_qa(session)["flagged"] == 0
        assert "not-opportunity" not in session.get(RssItem, job.id).flags
    finally:
        session.close()
