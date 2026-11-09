"""The agent's tools — the UniCompass MCP server, run in-process.

The same tool definitions serve external assistants (Claude Desktop, Cursor)
over stdio and the in-app agent here: one source of truth for names, schemas,
descriptions and behaviour.

In-process wiring: the MCP server's HTTP client gets an ASGI transport that
calls this FastAPI app directly (no network hop), authenticated with the
chatting user's own JWT — so the agent can only do what that user's API
access allows.
"""

from __future__ import annotations

import json
from contextlib import AsyncExitStack
from typing import Any

import httpx
from mcp import Client
from unicompass_mcp.api import Credentials, UniCompassAPI
from unicompass_mcp.server import create_server

from app.services.agent.mcp_clients import ExternalTools
from app.services.agent.providers import ToolCall, ToolOutcome, ToolSpec

MAX_RESULT_CHARS = 12_000


class Toolbox:
    def __init__(self, asgi_app: Any, user_token: str) -> None:
        self._asgi_app = asgi_app
        self._token = user_token
        self._stack: AsyncExitStack | None = None
        self._client: Client | None = None
        self.specs: list[ToolSpec] = []
        self._external = ExternalTools()

    async def __aenter__(self) -> "Toolbox":
        def api_factory() -> UniCompassAPI:
            return UniCompassAPI(
                "http://unicompass.internal",
                Credentials(token=self._token),
                transport=httpx.ASGITransport(app=self._asgi_app),
            )

        self._stack = AsyncExitStack()
        self._client = await self._stack.enter_async_context(Client(create_server(api_factory)))
        listed = await self._client.list_tools()
        self.specs = [
            ToolSpec(name=t.name, description=t.description or "", input_schema=t.input_schema)
            for t in listed.tools
        ]
        await self._external.start(self._stack)  # optional servers; failures are skipped, not raised
        self.specs += self._external.specs
        return self

    async def __aexit__(self, *exc) -> None:
        if self._stack is not None:
            await self._stack.aclose()

    async def call(self, call: ToolCall) -> ToolOutcome:
        if call.arguments is None:
            return ToolOutcome(
                call,
                f"Invalid JSON arguments for {call.name}: {call.raw_arguments[:200]!r}. "
                "Retry with a valid JSON object.",
                is_error=True,
            )
        assert self._client is not None, "Toolbox used outside 'async with'"
        if self._external.owns(call.name):
            try:
                text, is_error = await self._external.call(call.name, call.arguments)
            except Exception as exc:  # noqa: BLE001 — surfaced to the model as a tool error
                return ToolOutcome(call, f"{call.name} failed: {exc.__class__.__name__}", is_error=True)
            if len(text) > MAX_RESULT_CHARS:
                text = text[:MAX_RESULT_CHARS] + " …[truncated]"
            return ToolOutcome(call, text, is_error=is_error)
        result = await self._client.call_tool(call.name, call.arguments)
        if result.is_error:
            text = " ".join(getattr(c, "text", "") for c in result.content).strip()
            return ToolOutcome(call, text or f"{call.name} failed", is_error=True)

        data = result.structured_content
        if data is not None:
            if set(data) == {"result"}:
                data = data["result"]
            text = json.dumps(data, ensure_ascii=False, default=str)
        else:
            text = " ".join(getattr(c, "text", "") for c in result.content)
        if len(text) > MAX_RESULT_CHARS:
            text = text[:MAX_RESULT_CHARS] + " …[truncated — narrow the query or lower `limit`]"
        return ToolOutcome(call, text)
