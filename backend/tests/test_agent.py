"""Compass Agent tests.

A scripted provider stands in for the LLM; everything else is real: the
loop, the in-process MCP server, the API it calls (as the chatting user),
and the database.
"""

from __future__ import annotations

import json
from typing import Any, Callable

import httpx
import pytest

from app.services.agent import providers
from app.services.agent.providers import (
    AnthropicProvider,
    GroqProvider,
    LLMProvider,
    ProviderError,
    ToolCall,
    ToolOutcome,
    Turn,
)
from tests.conftest import make_item, register

Step = Callable[[list[dict[str, Any]]], Turn]


class ScriptedProvider(LLMProvider):
    """OpenAI-shaped messages (like Groq); each turn comes from a script step."""

    name = "scripted"

    def __init__(self, steps: list[Step]) -> None:
        self.model = "scripted-1"
        self.steps = list(steps)
        self.seen: list[list[dict[str, Any]]] = []
        self.tool_names: list[str] = []

    async def stream_turn(self, *, system, history, tools, on_text):
        self.seen.append(history)
        self.tool_names = [t.name for t in tools]
        if not self.steps:
            raise AssertionError("provider called more times than scripted")
        turn = self.steps.pop(0)(history)
        if turn.text:
            for word in turn.text.split(" "):
                await on_text(word + " ")
        return turn

    user_message = GroqProvider.user_message
    tool_result_messages = GroqProvider.tool_result_messages
    visible = GroqProvider.visible


def tool_turn(*calls: tuple[str, dict | None], text: str = "") -> Step:
    def step(history):
        tcs = [
            ToolCall(id=f"call_{i}", name=name, arguments=args, raw_arguments=json.dumps(args) if args is not None else "{bad")
            for i, (name, args) in enumerate(calls)
        ]
        msg = {
            "role": "assistant",
            "content": text or None,
            "tool_calls": [
                {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.raw_arguments}}
                for c in tcs
            ],
        }
        return Turn(assistant_message=msg, text=text, tool_calls=tcs, stop="tool_use")

    return step


def answer(text: str | Callable[[list[dict]], str]) -> Step:
    def step(history):
        t = text(history) if callable(text) else text
        return Turn(assistant_message={"role": "assistant", "content": t}, text=t, stop="end")

    return step


def failing(message: str) -> Step:
    def step(history):
        raise ProviderError(message)

    return step


def last_tool_payload(history) -> Any:
    return json.loads(next(m for m in reversed(history) if m["role"] == "tool")["content"])


def sse_events(resp: httpx.Response) -> list[dict]:
    return [
        json.loads(chunk[len("data: "):])
        for chunk in resp.text.split("\n\n")
        if chunk.startswith("data: ")
    ]


@pytest.fixture
def use_provider(monkeypatch):
    holder: dict[str, ScriptedProvider] = {}

    def install(*steps: Step) -> ScriptedProvider:
        provider = ScriptedProvider(list(steps))
        holder["p"] = provider
        monkeypatch.setattr("app.routers.agent.provider_for", lambda name=None: provider)
        return provider

    return install


def chat(client, headers, message, conversation_id=None):
    body = {"message": message}
    if conversation_id is not None:
        body["conversation_id"] = conversation_id
    resp = client.post("/agent/chat", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    return sse_events(resp)


# ── End-to-end through real tools ────────────────────────────────────────────

def test_search_then_answer_streams_and_persists(client, auth_headers, seed_items, use_provider):
    seed_items(
        make_item(url="https://ex.com/ml", title="Machine Learning Intern", tags=["machine learning"]),
        make_item(url="https://ex.com/fe", title="Frontend Intern"),
    )
    provider = use_provider(
        tool_turn(("search_opportunities", {"query": "machine learning", "limit": 5})),
        answer(lambda h: "Top pick: " + last_tool_payload(h)["results"][0]["title"]),
    )

    events = chat(client, auth_headers, "Find me ML internships")
    types = [e["type"] for e in events]
    assert types[0] == "conversation" and types[-1] == "done"
    assert events[-1]["stop"] == "end"

    call = next(e for e in events if e["type"] == "tool_call")
    result = next(e for e in events if e["type"] == "tool_result")
    assert call["name"] == "search_opportunities" and result["ok"] is True
    assert result["preview"][0]["title"] == "Machine Learning Intern"  # real ranking, real DB
    text = "".join(e["delta"] for e in events if e["type"] == "text")
    assert text.strip() == "Top pick: Machine Learning Intern"
    assert "bookmark_opportunity" in provider.tool_names  # MCP tools exposed

    conv = client.get(f"/agent/conversations/{events[0]['id']}", headers=auth_headers).json()
    assert [m["role"] for m in conv["messages"]] == ["user", "assistant"]
    assert conv["messages"][1]["tool_calls"][0]["name"] == "search_opportunities"
    assert conv["messages"][1]["text"] == "Top pick: Machine Learning Intern"


def test_tools_act_as_the_chatting_user(client, seed_items, use_provider):
    (item,) = seed_items(make_item())
    alice, bob = register(client, "alice@ex.com"), register(client, "bob@ex.com")
    use_provider(tool_turn(("bookmark_opportunity", {"id": item.id})), answer("Saved."))

    chat(client, alice, "save it")
    assert client.get("/api/bookmarks/ids", headers=alice).json() == {"ids": [item.id]}
    assert client.get("/api/bookmarks/ids", headers=bob).json() == {"ids": []}


def test_follow_up_sees_prior_history(client, auth_headers, use_provider):
    provider = use_provider(answer("Hi! What are you looking for?"), answer("Got it."))
    first = chat(client, auth_headers, "hello")
    chat(client, auth_headers, "internships please", conversation_id=first[0]["id"])

    second_history = provider.seen[1]
    assert [m["role"] for m in second_history] == ["user", "assistant", "user"]
    assert second_history[0]["content"] == "hello"


def test_tool_error_is_fed_back_not_raised(client, auth_headers, use_provider):
    provider = use_provider(
        tool_turn(("get_opportunity", {"id": 424242}), ("search_opportunities", None)),
        answer("Couldn't find that one."),
    )
    events = chat(client, auth_headers, "open 424242")
    results = [e for e in events if e["type"] == "tool_result"]
    assert [r["ok"] for r in results] == [False, False]
    tool_msgs = [m for m in provider.seen[1] if m["role"] == "tool"]
    assert "Not found" in tool_msgs[0]["content"]
    assert "Invalid JSON" in tool_msgs[1]["content"]
    assert events[-1]["stop"] == "end"


# ── Limits, failures, isolation ──────────────────────────────────────────────

def test_step_limit_grants_one_final_answer(client, auth_headers, use_provider, monkeypatch):
    monkeypatch.setattr("app.config.settings.AGENT_MAX_TOOL_ROUNDS", 2)
    loop_call = ("list_bookmarks", {})
    provider = use_provider(
        tool_turn(loop_call), tool_turn(loop_call),  # rounds 0, 1 run
        tool_turn(loop_call),                         # blocked: told to stop
        answer("Here is what I found so far."),       # the granted final turn
    )
    events = chat(client, auth_headers, "keep going")
    assert [r["ok"] for r in events if r["type"] == "tool_result"] == [True, True, False]
    assert events[-1]["stop"] == "end"
    blocked = [m for m in provider.seen[3] if m["role"] == "tool"][-1]["content"]
    assert "Step limit reached" in blocked


def test_step_limit_stops_a_model_that_ignores_it(client, auth_headers, use_provider, monkeypatch):
    monkeypatch.setattr("app.config.settings.AGENT_MAX_TOOL_ROUNDS", 1)
    call = ("get_profile", {})
    use_provider(tool_turn(call), tool_turn(call), tool_turn(call))
    events = chat(client, auth_headers, "loop forever")
    assert events[-1]["stop"] == "step_limit"

    # Every stored tool call has a result, so the conversation stays usable.
    conv_id = events[0]["id"]
    from app.db import SessionLocal
    from app.repositories.agent_repository import AgentRepository

    db = SessionLocal()
    try:
        msgs = AgentRepository(db).messages(conv_id)
    finally:
        db.close()
    asked = {c["id"] for m in msgs for c in m.get("tool_calls") or []}
    answered = {m["tool_call_id"] for m in msgs if m["role"] == "tool"}
    assert asked and asked == answered


def test_provider_failure_persists_nothing_and_can_retry(client, auth_headers, use_provider):
    use_provider(failing("Groq is rate-limiting requests; try again shortly."), answer("Hello again."))
    events = chat(client, auth_headers, "hi")
    assert {"type": "error", "message": "Groq is rate-limiting requests; try again shortly."} in events
    conv_id = events[0]["id"]
    assert client.get(f"/agent/conversations/{conv_id}", headers=auth_headers).json()["messages"] == []
    # The empty chat stays out of the sidebar until something is saved in it.
    assert client.get("/agent/conversations", headers=auth_headers).json() == []

    chat(client, auth_headers, "hi", conversation_id=conv_id)
    assert [c["id"] for c in client.get("/agent/conversations", headers=auth_headers).json()] == [conv_id]
    roles = [m["role"] for m in client.get(f"/agent/conversations/{conv_id}", headers=auth_headers).json()["messages"]]
    assert roles == ["user", "assistant"]


def test_conversations_are_private(client, auth_headers, use_provider):
    use_provider(answer("hi"))
    conv_id = chat(client, auth_headers, "hello")[0]["id"]
    other = register(client, "other@ex.com")
    assert client.get(f"/agent/conversations/{conv_id}", headers=other).status_code == 404
    assert client.post("/agent/chat", json={"message": "x", "conversation_id": conv_id}, headers=other).status_code == 404
    assert client.get("/agent/conversations", headers=other).json() == []
    assert client.delete(f"/agent/conversations/{conv_id}", headers=auth_headers).json() == {"deleted": conv_id}


def test_chat_requires_login(client, db):
    assert client.post("/agent/chat", json={"message": "hi"}).status_code == 401


def test_unknown_provider_is_503(client, auth_headers, monkeypatch):
    monkeypatch.setattr("app.config.settings.AGENT_PROVIDER", "nope")
    resp = client.post("/agent/chat", json={"message": "hi"}, headers=auth_headers)
    assert resp.status_code == 503


# ── Provider adapters ────────────────────────────────────────────────────────

def _groq_sse(*chunks: dict) -> bytes:
    lines = [f"data: {json.dumps({'choices': [c]})}" for c in chunks] + ["data: [DONE]"]
    return ("\n\n".join(lines) + "\n\n").encode()


@pytest.mark.anyio
async def test_groq_stream_assembles_split_tool_calls(monkeypatch):
    monkeypatch.setattr(providers.settings, "GROQ_API_KEY", "test-key")
    body = _groq_sse(
        {"delta": {"content": "Let me look"}},
        {"delta": {"tool_calls": [{"index": 0, "id": "c1", "function": {"name": "search_", "arguments": '{"que'}}]}},
        {"delta": {"tool_calls": [{"index": 0, "function": {"name": "opportunities", "arguments": 'ry": "ml"}'}}]}},
        {"delta": {}, "finish_reason": "tool_calls"},
    )
    seen = {}

    def handler(request: httpx.Request):
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    deltas = []

    async def on_text(d):
        deltas.append(d)

    provider = GroqProvider("llama-test", transport=httpx.MockTransport(handler))
    turn = await provider.stream_turn(system="sys", history=[{"role": "user", "content": "hi"}], tools=[], on_text=on_text)

    assert seen["auth"] == "Bearer test-key"
    assert seen["body"]["messages"][0] == {"role": "system", "content": "sys"}
    assert deltas == ["Let me look"]
    assert turn.stop == "tool_use"
    assert (turn.tool_calls[0].name, turn.tool_calls[0].arguments) == ("search_opportunities", {"query": "ml"})
    assert turn.assistant_message["tool_calls"][0]["function"]["arguments"] == '{"query": "ml"}'


@pytest.mark.anyio
async def test_groq_errors_are_readable(monkeypatch):
    monkeypatch.setattr(providers.settings, "GROQ_API_KEY", "bad")
    provider = GroqProvider(transport=httpx.MockTransport(lambda r: httpx.Response(401, json={"error": "x"})))

    async def noop(_):
        pass

    with pytest.raises(ProviderError, match="GROQ_API_KEY"):
        await provider.stream_turn(system="s", history=[], tools=[], on_text=noop)


def test_anthropic_message_shapes():
    provider = AnthropicProvider.__new__(AnthropicProvider)  # shapes only, no client
    call = ToolCall(id="toolu_1", name="get_profile", arguments={})
    (msg,) = provider.tool_result_messages(
        [ToolOutcome(call, '{"skills": []}'), ToolOutcome(ToolCall("toolu_2", "x", {}), "boom", is_error=True)]
    )
    assert msg["role"] == "user"
    assert [b["tool_use_id"] for b in msg["content"]] == ["toolu_1", "toolu_2"]
    assert "is_error" not in msg["content"][0] and msg["content"][1]["is_error"] is True

    assert provider.visible(msg) is None
    assistant = {"role": "assistant", "content": [
        {"type": "thinking", "thinking": "", "signature": "sig"},
        {"type": "text", "text": "Checking."},
        {"type": "tool_use", "id": "toolu_1", "name": "get_profile", "input": {}},
    ]}
    assert provider.visible(assistant) == {
        "role": "assistant", "text": "Checking.", "tool_calls": [{"name": "get_profile", "arguments": {}}],
    }
