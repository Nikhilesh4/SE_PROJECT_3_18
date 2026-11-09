import json

from app.config import settings
from app.services.discovery import fetcher, source_scout
from app.services.rss import feed_sources

RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>Acme Careers</title>{items}</channel></rss>"""
ITEM = "<item><title>{t}</title><description>{d}</description><link>https://acme.io/{n}</link></item>"
GOOD = RSS.format(items="".join(ITEM.format(t=f"Software Engineer Intern {n}", d="We are hiring. Apply now for this internship.", n=n) for n in range(5)))
BLOG = RSS.format(items="".join(ITEM.format(t=f"Top {n} ways to ace interviews", d="Tips and tricks.", n=n) for n in range(5)))


def fake_fetch(pages):
    def fetch(url, **kw):
        if url in pages:
            return fetcher.Page(url, 200, pages[url], "text/html")
        return fetcher.Page(url, 404, "", "text/html")
    return fetch


def test_scout_finds_linked_and_common_feeds_and_rejects_blogs():
    pages = {
        "https://acme.io/": '<html><head><link rel="alternate" type="application/rss+xml" href="/jobs.xml"></head></html>',
        "https://acme.io/jobs.xml": GOOD,
        "https://acme.io/rss": BLOG,
    }
    found = source_scout.scout_site("https://acme.io/", fetch=fake_fetch(pages))
    assert [p.url for p in found] == ["https://acme.io/jobs.xml"]
    assert found[0].suggested_category == "internship" and found[0].pass_rate >= 0.5 and not found[0].already_configured


def test_scout_survives_blocked_feed_urls():
    def fetch(url, **kw):
        if url.endswith("/feed"):
            raise fetcher.FetchBlocked("robots")
        return fetcher.Page(url, 200, GOOD if url.endswith("/rss") else "<html></html>", "text/html")
    assert [p.url for p in source_scout.scout_site("https://acme.io/", fetch=fetch)] == ["https://acme.io/rss"]


def test_approval_writes_file_and_is_loaded(tmp_path, monkeypatch):
    path = tmp_path / "approved.json"
    monkeypatch.setattr(source_scout, "APPROVED_FEEDS_PATH", path)
    source_scout.approve("https://acme.io/jobs.xml", "internship", "Acme Careers")
    source_scout.approve("https://acme.io/jobs.xml", "internship", "Acme Careers")  # idempotent
    assert len(json.loads(path.read_text())) == 1
    loaded = feed_sources.load_approved_feeds(path)
    assert loaded[0].category == "internship" and loaded[0].source_name == "Acme Careers"
    path.write_text(json.dumps([{"url": "ftp://x", "category": "job", "source_name": "bad"}, {"url": "https://ok.io/f", "category": "nope", "source_name": "x"}]))
    assert feed_sources.load_approved_feeds(path) == ()  # invalid entries ignored


def test_admin_flow_over_http(client, auth_headers, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", "student@example.com")
    monkeypatch.setattr(source_scout, "APPROVED_FEEDS_PATH", tmp_path / "a.json")
    monkeypatch.setattr(source_scout, "scout_site", lambda url: [source_scout.Proposal("https://acme.io/jobs.xml", "Acme", 5, 1.0, "internship", ["x"])])

    run = client.post("/api/discovery/source-scout", headers=auth_headers, json={"url": "https://acme.io/"}).json()
    assert run["proposals"][0]["url"] == "https://acme.io/jobs.xml"
    assert client.post(f"/api/discovery/source-proposals/{run['id']}/approve", headers=auth_headers).json()["approved"] == "https://acme.io/jobs.xml"
    assert client.get("/api/discovery/source-proposals", headers=auth_headers).json()["proposals"][0]["status"] == "approved"
    assert client.post(f"/api/discovery/source-proposals/{run['id']}/approve?feed_index=5", headers=auth_headers).status_code == 404

    monkeypatch.setattr(settings, "ADMIN_EMAILS", "")
    assert client.post("/api/discovery/source-scout", headers=auth_headers, json={"url": "https://acme.io/"}).status_code == 403


def test_blocked_site_is_refused(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", "student@example.com")
    r = client.post("/api/discovery/source-scout", headers=auth_headers, json={"url": "http://127.0.0.1:8000/"})
    assert r.status_code == 400 and "Refused" in r.json()["detail"]
