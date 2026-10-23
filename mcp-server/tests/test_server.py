"""MCP server tests: real MCP protocol (in-process Client) against a fake backend.

The fake implements just enough of the FastAPI contract (paths, auth, status
codes) to exercise the server's behaviour without Postgres or the model.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from mcp import Client

from unicompass_mcp.api import Credentials, UniCompassAPI
from unicompass_mcp.server import create_server

NOW = datetime.now(timezone.utc)
pytestmark = pytest.mark.anyio


class FakeBackend:
    def __init__(self) -> None:
        self.items = {
            1: {"id": 1, "title": "ML Research Intern", "category": "research",
                "summary": "Train&#160;<b>vision</b> models.", "url": "https://ex.com/1",
                "source_name": "Lab", "tags": ["ml"],
                "application_deadline": (NOW + timedelta(days=3)).isoformat()},
            2: {"id": 2, "title": "React Developer", "category": "job", "summary": "UI work.",
                "url": "https://ex.com/2", "source_name": "Board", "tags": [],
                "application_deadline": (NOW + timedelta(days=40)).isoformat()},
            3: {"id": 3, "title": "Old Hackathon", "category": "hackathon", "summary": "",
                "url": "https://ex.com/3", "source_name": "HE", "tags": [],
                "application_deadline": (NOW - timedelta(days=1)).isoformat()},
        }
        self.profile: dict | None = {"skills": ["Python", "PyTorch"], "interests": ["Vision"],
                                     "education": [], "experience": [], "from_cache": False}
        self.bookmarks: list[int] = []
        self.valid_tokens = {"tok-1"}
        self.logins = 0
        self.feed_calls: list[dict] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path, method = request.url.path, request.method
        if path == "/auth/login":
            body = json.loads(request.content)
            if body == {"email": "s@ex.com", "password": "pw"}:
                self.logins += 1
                token = f"tok-{self.logins}"
                self.valid_tokens.add(token)
                return httpx.Response(200, json={"access_token": token, "token_type": "bearer"})
            return httpx.Response(401, json={"detail": "Invalid email or password"})

        if path == "/api/feeds/rss":
            params = dict(request.url.params)
            self.feed_calls.append(params)
            items = list(self.items.values())
            if params.get("category"):
                items = [i for i in items if i["category"] == params["category"]]
            if params.get("active_only") == "true":
                items = [i for i in items if i["application_deadline"] > NOW.isoformat()]
            return httpx.Response(200, json={"items": items, "sources": [], "total_items": len(items),
                                             "fetched_at": NOW.isoformat(), "from_cache": False})
        if path.startswith("/api/feeds/items/"):
            item = self.items.get(int(path.rsplit("/", 1)[1]))
            return httpx.Response(200, json=item) if item else httpx.Response(404, json={"detail": "Opportunity not found."})

        # Everything below needs auth
        token = request.headers.get("Authorization", "").removeprefix("Bearer ")
        if token not in self.valid_tokens:
            return httpx.Response(401, json={"detail": "Could not validate credentials"})

        if path == "/profile/me" and method == "GET":
            if self.profile is None:
                return httpx.Response(404, json={"detail": "No profile found."})
            return httpx.Response(200, json=self.profile)
        if path == "/profile/me" and method == "PATCH":
            self.profile.update(json.loads(request.content))
            return httpx.Response(200, json=self.profile)
        if path == "/api/bookmarks/ids":
            return httpx.Response(200, json={"ids": self.bookmarks})
        if path == "/api/bookmarks":
            return httpx.Response(200, json=[self.items[i] for i in reversed(self.bookmarks)])
        if path.startswith("/api/bookmarks/"):
            item_id = int(path.rsplit("/", 1)[1])
            if method == "DELETE":
                if item_id in self.bookmarks:
                    self.bookmarks.remove(item_id)
                return httpx.Response(200, json={"action": "removed", "rss_item_id": item_id})
            if item_id not in self.items:
                return httpx.Response(404, json={"detail": "Opportunity not found."})
            if item_id in self.bookmarks:
                self.bookmarks.remove(item_id)
                return httpx.Response(200, json={"action": "removed", "rss_item_id": item_id})
            self.bookmarks.append(item_id)
            return httpx.Response(200, json={"action": "added", "rss_item_id": item_id})
        return httpx.Response(404, json={"detail": "Not Found"})


@pytest.fixture
def backend():
    return FakeBackend()


def make_client(backend: FakeBackend, credentials: Credentials | None = None) -> Client:
    creds = credentials or Credentials(email="s@ex.com", password="pw")
    server = create_server(
        lambda: UniCompassAPI("http://test", creds, transport=httpx.MockTransport(backend.handler))
    )
    return Client(server)


async def call(client: Client, tool: str, **args):
    result = await client.call_tool(tool, args)
    if result.is_error:
        return {"error": result.content[0].text}
    data = result.structured_content
    return data["result"] if set(data) == {"result"} else data


# ── Discovery ────────────────────────────────────────────────────────────────

async def test_search_without_query_ranks_by_profile(backend):
    async with make_client(backend) as client:
        out = await call(client, "search_opportunities")
    assert out["ranked_by"] == "profile"
    assert backend.feed_calls[-1]["skills"] == "Python,PyTorch,Vision"
    assert {r["id"] for r in out["results"]} == {1, 2}  # expired item hidden


async def test_search_with_query_uses_query_not_profile(backend):
    async with make_client(backend) as client:
        out = await call(client, "search_opportunities", query="react, typescript", category="job")
    assert out["ranked_by"] == "query"
    assert backend.feed_calls[-1]["skills"] == "react,typescript"
    assert backend.feed_calls[-1]["category"] == "job"


async def test_search_falls_back_to_newest_without_profile(backend):
    backend.profile = None
    async with make_client(backend) as client:
        out = await call(client, "search_opportunities", include_expired=True)
    assert out["ranked_by"] == "newest"
    assert "skills" not in backend.feed_calls[-1]
    assert out["total_matches"] == 3


async def test_results_have_plain_text_summaries(backend):
    async with make_client(backend) as client:
        out = await call(client, "get_opportunity", id=1)
    assert out["summary"] == "Train vision models."
    assert out["bookmarked"] is False


async def test_invalid_category_rejected_by_schema(backend):
    async with make_client(backend) as client:
        out = await call(client, "search_opportunities", category="party")
    assert "error" in out


async def test_unknown_opportunity_is_readable_error(backend):
    async with make_client(backend) as client:
        out = await call(client, "get_opportunity", id=999)
    assert out["error"].endswith("Not found: Opportunity not found.")


# ── Bookmarks & deadlines ────────────────────────────────────────────────────

async def test_bookmark_is_idempotent(backend):
    """The backend only toggles; the tool must never un-save on a repeat call."""
    async with make_client(backend) as client:
        first = await call(client, "bookmark_opportunity", id=1)
        second = await call(client, "bookmark_opportunity", id=1)
        listed = await call(client, "list_bookmarks")
    assert first["changed"] is True and second["changed"] is False
    assert backend.bookmarks == [1]
    assert [b["id"] for b in listed] == [1]


async def test_remove_bookmark_reports_change(backend):
    backend.bookmarks = [2]
    async with make_client(backend) as client:
        assert (await call(client, "remove_bookmark", id=2))["changed"] is True
        assert (await call(client, "remove_bookmark", id=2))["changed"] is False


async def test_upcoming_deadlines_filters_and_sorts(backend):
    backend.bookmarks = [2, 3, 1]
    async with make_client(backend) as client:
        week = await call(client, "upcoming_deadlines", days=7)
        quarter = await call(client, "upcoming_deadlines", days=90)
    assert [d["id"] for d in week] == [1]  # 2 is too far out, 3 already passed
    assert [d["id"] for d in quarter] == [1, 2]
    assert week[0]["days_left"] in (2, 3)


# ── Profile ──────────────────────────────────────────────────────────────────

async def test_update_profile_adds_and_removes_case_insensitively(backend):
    async with make_client(backend) as client:
        out = await call(client, "update_profile", add_skills=["Rust"], remove_skills=["pytorch"])
    assert out["skills"] == ["Python", "Rust"]
    assert out["interests"] == ["Vision"]


async def test_get_profile_hides_cache_flag(backend):
    async with make_client(backend) as client:
        out = await call(client, "get_profile")
    assert "from_cache" not in out and out["skills"] == ["Python", "PyTorch"]


# ── Auth ─────────────────────────────────────────────────────────────────────

async def test_relogs_in_when_token_expires(backend):
    async with make_client(backend) as client:
        await call(client, "get_profile")
        backend.valid_tokens.clear()  # simulate 24h expiry
        out = await call(client, "get_profile")
    assert out["skills"] and backend.logins == 2


async def test_missing_credentials_explain_setup(backend):
    async with make_client(backend, Credentials()) as client:
        out = await call(client, "list_bookmarks")
    assert "UNICOMPASS_EMAIL" in out["error"]


async def test_wrong_password_is_reported(backend):
    async with make_client(backend, Credentials(email="s@ex.com", password="nope")) as client:
        out = await call(client, "get_profile")
    assert out["error"].endswith("UniCompass API error 401: Invalid email or password")


async def test_backend_down_is_reported(backend):
    def down(request):
        raise httpx.ConnectError("refused", request=request)

    server = create_server(
        lambda: UniCompassAPI("http://test", Credentials(token="t"), transport=httpx.MockTransport(down))
    )
    async with Client(server) as client:
        out = await call(client, "search_opportunities", query="x")
    assert "Cannot reach the UniCompass backend" in out["error"]


# ── Resources & prompts ──────────────────────────────────────────────────────

async def test_resources_and_prompts(backend):
    backend.bookmarks = [1]
    async with make_client(backend) as client:
        profile = await client.read_resource("unicompass://profile")
        bookmarks = await client.read_resource("unicompass://bookmarks")
        prompt = await client.get_prompt("skill_gap", {"id": "1"})
    assert json.loads(profile.contents[0].text)["skills"] == ["Python", "PyTorch"]
    assert json.loads(bookmarks.contents[0].text)[0]["id"] == 1
    text = prompt.messages[0].content.text
    assert "ML Research Intern" in text and "PyTorch" in text and "untrusted" in text
