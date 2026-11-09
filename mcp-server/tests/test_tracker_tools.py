"""Tracker / notification / mission / insights / coaching tools, over the real MCP protocol with a fake backend."""

from __future__ import annotations

import json

import httpx
import pytest
from mcp import Client

from unicompass_mcp.api import Credentials, UniCompassAPI
from unicompass_mcp.server import create_server

pytestmark = pytest.mark.anyio

ITEM = {"id": 1, "title": "ML Intern", "category": "internship", "summary": "Python", "url": "https://e.com/1", "source_name": "S", "tags": [],
        "application_deadline": None, "remote": True, "stipend_inr_month": 30000.0}


class Backend:
    def __init__(self):
        self.calls: list[tuple[str, str, object]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        self.calls.append((request.method, request.url.path, body or dict(request.url.params)))
        path = request.url.path
        if request.headers.get("authorization") != "Bearer tok" and path not in ("/api/search", "/api/insights/trends"):
            return httpx.Response(401, json={"detail": "no"})
        routes = {
            ("GET", "/api/applications"): {"total": 2, "statuses": [], "columns": {
                "saved": [{"item": ITEM, "notes": "n", "status": "saved"}], "applied": [{"item": {**ITEM, "id": 2, "title": "B"}, "notes": "", "status": "applied"}]}},
            ("PATCH", "/api/applications/1"): {"status": body and body.get("status", "saved"), "notes": (body or {}).get("notes", ""), "applied_at": "2026-11-09"},
            ("GET", "/api/notifications"): {"unread": 1, "notifications": [{"id": 1, "kind": "deadline", "title": "Closing", "body": "b", "rss_item_id": 1, "created_at": "x", "read": False}]},
            ("GET", "/api/standup"): {"facts": {"saved": 1, "applied": 0, "actions": ["x"]}, "text": "t",
                                      "actions": [{"kind": "deadline", "text": "Apply to ML Intern before 12 Nov", "priority": 2, "item_id": 1}]},
            ("GET", "/api/missions"): {"missions": [{"id": 3, "name": "ML"}]},
            ("POST", "/api/missions"): {"id": 3, "name": (body or {}).get("name"), "remote_only": True},
            ("POST", "/api/missions/3/run"): {"new_matches": [{"id": 1}]},
            ("GET", "/api/insights/items/1"): {"skill_gap": {"coverage": 50}},
            ("GET", "/api/search"): {"total": 1, "facets": {}, "items": [ITEM]},
            ("GET", "/api/insights/trends"): {"top_skills": [{"skill": "python", "postings": 3}]},
            ("GET", "/api/insights/company"): {"company": "Acme", "open_postings": 2},
            ("GET", "/api/insights/projects"): {"projects": [{"skill": "docker", "idea": "x"}]},
            ("POST", "/api/outreach/draft"): {"subject": "s", "body": "b", "review_note": "draft"},
            ("POST", "/api/interview/questions"): {"questions": [{"question": "q", "topic": "t"}]},
            ("POST", "/api/research/scout"): {"papers": [], "contacts": []},
            ("GET", "/api/memory/search"): {"results": [{"item_id": 1, "notes": "Maya said"}]},
        }
        data = routes.get((request.method, path))
        return httpx.Response(200, json=data) if data is not None else httpx.Response(404, json={"detail": "Opportunity not found."})


@pytest.fixture
async def session():
    backend = Backend()
    api = lambda: UniCompassAPI("http://t", Credentials(token="tok"), transport=httpx.MockTransport(backend.handler))
    async with Client(create_server(api)) as client:
        yield client, backend


async def call(client, name, args=None):
    r = await client.call_tool(name, args or {})
    assert not r.is_error, r.content
    return r.structured_content["result"] if set(r.structured_content) == {"result"} else r.structured_content


async def test_all_new_tools_are_listed(session):
    client, _ = session
    names = {t.name for t in (await client.list_tools()).tools}
    assert {"list_applications", "update_application", "get_notifications", "list_missions", "create_mission", "run_mission", "explain_opportunity",
            "search_with_filters", "skill_demand_trends", "company_brief", "suggest_projects", "interview_questions", "draft_outreach",
            "research_scout", "search_my_notes"} <= names


async def test_applications_and_update(session):
    client, backend = session
    board = await call(client, "list_applications")
    assert board["total"] == 2 and board["columns"]["saved"][0]["notes"] == "n"
    only = await call(client, "list_applications", {"status": "applied"})
    assert list(only["columns"]) == ["applied"]
    moved = await call(client, "update_application", {"id": 1, "status": "applied", "notes": "sent"})
    assert moved["status"] == "applied" and ("PATCH", "/api/applications/1", {"status": "applied", "notes": "sent"}) in backend.calls
    bad = await client.call_tool("update_application", {"id": 1, "status": "dancing"})
    assert bad.is_error


async def test_notifications_missions_and_insights(session):
    client, _ = session
    n = await call(client, "get_notifications")
    assert n["unread"] == 1 and n["notifications"][0]["kind"] == "deadline"
    assert (await call(client, "list_missions"))[0]["name"] == "ML"
    assert (await call(client, "create_mission", {"name": "ML", "query": "remote ml internships"}))["remote_only"] is True
    assert (await call(client, "run_mission", {"id": 3}))["new_matches"] == [{"id": 1}]
    assert (await call(client, "explain_opportunity", {"id": 1}))["skill_gap"]["coverage"] == 50
    found = await call(client, "search_with_filters", {"query": "ml", "remote": True, "min_stipend_inr_per_month": 20000})
    assert found["results"][0]["stipend_inr_month"] == 30000.0
    assert (await call(client, "skill_demand_trends"))["top_skills"][0]["skill"] == "python"


async def test_coaching_tools(session):
    client, backend = session
    assert (await call(client, "company_brief", {"name": "Acme"}))["open_postings"] == 2
    assert (await call(client, "suggest_projects", {"id": 1}))["projects"][0]["skill"] == "docker"
    assert (await call(client, "draft_outreach", {"kind": "cold_email", "id": 1, "recipient": "Priya"}))["review_note"] == "draft"
    assert ("POST", "/api/outreach/draft", {"kind": "cold_email", "recipient": "Priya", "item_id": 1}) in backend.calls
    assert (await call(client, "interview_questions", {"role": "Backend"}))["questions"][0]["topic"] == "t"
    assert "papers" in await call(client, "research_scout", {"topic": "attention"})
    assert (await call(client, "search_my_notes", {"query": "maya"}))[0]["notes"] == "Maya said"
    missing = await client.call_tool("explain_opportunity", {"id": 99})
    assert missing.is_error and "Not found" in missing.content[0].text


async def test_career_standup_returns_facts_and_ranked_actions(session):
    client, backend = session
    s = await call(client, "career_standup")
    assert s["next_actions"] == ["Apply to ML Intern before 12 Nov"]
    assert s["facts"]["saved"] == 1 and "actions" not in s["facts"]  # the duplicate action list is dropped
    assert ("GET", "/api/standup", {"polish": "false"}) in backend.calls
