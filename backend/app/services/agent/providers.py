"""LLM provider adapters for the Compass Agent.

Architecture Patterns Used:
  - Adapter / Strategy: LLMProvider gives the agent loop one interface over
    Groq (OpenAI-compatible chat completions) and Claude (Anthropic Messages
    API), selected by AGENT_PROVIDER.

Each provider keeps messages in its own wire format; the loop treats them as
opaque dicts and only asks the provider to build, stream and inspect them.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import httpx

from app.config import settings

logger = logging.getLogger("agent.providers")

OnText = Callable[[str], Awaitable[None]]


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any] | None  # None → the model produced unparseable JSON
    raw_arguments: str = ""


@dataclass
class ToolOutcome:
    call: ToolCall
    content: str
    is_error: bool = False


@dataclass
class Turn:
    """One model response, normalised for the loop."""

    assistant_message: dict[str, Any]  # provider-native; appended to history as-is
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    # "end" | "tool_use" | "max_tokens" | "refusal"
    stop: str = "end"


class ProviderError(Exception):
    """A provider failure the user should see (bad key, rate limit, outage)."""


class LLMProvider(ABC):
    name: str
    model: str

    @abstractmethod
    async def stream_turn(
        self,
        *,
        system: str,
        history: list[dict[str, Any]],
        tools: list[ToolSpec],
        on_text: OnText,
    ) -> Turn:
        ...

    @abstractmethod
    def user_message(self, text: str) -> dict[str, Any]:
        ...

    @abstractmethod
    def tool_result_messages(self, outcomes: list[ToolOutcome]) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def visible(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """Render a stored message for the chat UI: {role, text, tool_calls}, or None to hide."""


# ── Claude (Anthropic Messages API) ──────────────────────────────────────────

class AnthropicProvider(LLMProvider):
    """
    Claude via the official SDK. Adaptive thinking is on (the only mode on
    Opus 5.5) at medium effort, which suits multi-step tool use in chat.
    Server-side refusal fallbacks ("default" routing) rerun a declined request
    on Anthropic's recommended fallback model inside the same call.
    """

    name = "anthropic"
    FALLBACK_BETA = "server-side-fallback-2026-07-01"

    def __init__(self, model: str | None = None) -> None:
        import anthropic

        self._anthropic = anthropic
        self.model = model or "claude-opus-5-5"
        # No explicit key: the SDK resolves ANTHROPIC_API_KEY / auth token / profile.
        self._client = anthropic.AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY or None
        )

    async def stream_turn(self, *, system, history, tools, on_text) -> Turn:
        anthropic = self._anthropic
        try:
            async with self._client.beta.messages.stream(
                model=self.model,
                max_tokens=16000,
                system=system,
                messages=history,
                tools=[
                    {"name": t.name, "description": t.description, "input_schema": t.input_schema}
                    for t in tools
                ],
                thinking={"type": "adaptive"},
                output_config={"effort": "medium"},
                betas=[self.FALLBACK_BETA],
                fallbacks="default",
            ) as stream:
                async for event in stream:
                    if event.type == "text":
                        await on_text(event.text)
                final = await stream.get_final_message()
        except anthropic.AuthenticationError as exc:
            raise ProviderError("Claude rejected the API key (check ANTHROPIC_API_KEY).") from exc
        except anthropic.RateLimitError as exc:
            raise ProviderError("Claude is rate-limiting requests; try again shortly.") from exc
        except anthropic.APIStatusError as exc:
            raise ProviderError(f"Claude API error {exc.status_code}.") from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderError("Could not reach the Claude API.") from exc

        # Append the full content unchanged — thinking blocks must round-trip.
        assistant = {
            "role": "assistant",
            "content": [b.model_dump(mode="json", exclude_none=True) for b in final.content],
        }
        calls = [
            ToolCall(id=b.id, name=b.name, arguments=b.input if isinstance(b.input, dict) else None)
            for b in final.content
            if b.type == "tool_use"
        ]
        text = "".join(b.text for b in final.content if b.type == "text")
        stop = {
            "tool_use": "tool_use",
            "max_tokens": "max_tokens",
            "refusal": "refusal",
        }.get(final.stop_reason or "", "end")
        if stop == "end" and calls:
            stop = "tool_use"
        return Turn(assistant_message=assistant, text=text, tool_calls=calls, stop=stop)

    def user_message(self, text: str) -> dict[str, Any]:
        return {"role": "user", "content": text}

    def tool_result_messages(self, outcomes):
        # All results for one turn go back in a single user message.
        return [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": o.call.id,
                        "content": o.content,
                        **({"is_error": True} if o.is_error else {}),
                    }
                    for o in outcomes
                ],
            }
        ]

    def visible(self, message):
        content = message.get("content")
        if isinstance(content, str):
            return {"role": message["role"], "text": content, "tool_calls": []}
        if message["role"] == "user":
            return None  # tool results
        return {
            "role": "assistant",
            "text": "".join(b.get("text", "") for b in content if b.get("type") == "text"),
            "tool_calls": [
                {"name": b["name"], "arguments": b.get("input", {})}
                for b in content
                if b.get("type") == "tool_use"
            ],
        }


# ── Groq (OpenAI-compatible chat completions) ────────────────────────────────

class GroqProvider(LLMProvider):
    """Groq's OpenAI-compatible endpoint, streamed over SSE with httpx."""

    name = "groq"
    URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, model: str | None = None, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.model = model or settings.GROQ_MODEL
        self._transport = transport

    async def stream_turn(self, *, system, history, tools, on_text) -> Turn:
        if not settings.GROQ_API_KEY:
            raise ProviderError("GROQ_API_KEY is not set.")

        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *history],
            "tools": [
                {
                    "type": "function",
                    "function": {"name": t.name, "description": t.description, "parameters": t.input_schema},
                }
                for t in tools
            ],
            "tool_choice": "auto",
            "temperature": 0.3,
            "max_tokens": 4096,
            "stream": True,
        }
        text_parts: list[str] = []
        calls: dict[int, dict[str, str]] = {}
        finish = None

        try:
            async with httpx.AsyncClient(timeout=60.0, transport=self._transport) as client:
                async with client.stream(
                    "POST",
                    self.URL,
                    json=body,
                    headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                ) as resp:
                    if resp.status_code >= 400:
                        detail = (await resp.aread()).decode(errors="replace")[:300]
                        raise ProviderError(_groq_error(resp.status_code, detail))
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data = line[6:].strip()
                        if data == "[DONE]":
                            break
                        choice = json.loads(data)["choices"][0]
                        delta = choice.get("delta", {})
                        if delta.get("content"):
                            text_parts.append(delta["content"])
                            await on_text(delta["content"])
                        for tc in delta.get("tool_calls") or []:
                            slot = calls.setdefault(tc["index"], {"id": "", "name": "", "arguments": ""})
                            slot["id"] = tc.get("id") or slot["id"]
                            fn = tc.get("function") or {}
                            slot["name"] += fn.get("name") or ""
                            slot["arguments"] += fn.get("arguments") or ""
                        finish = choice.get("finish_reason") or finish
        except httpx.HTTPError as exc:
            raise ProviderError("Could not reach the Groq API.") from exc

        tool_calls = []
        for slot in (calls[i] for i in sorted(calls)):
            try:
                args = json.loads(slot["arguments"] or "{}")
                args = args if isinstance(args, dict) else None
            except json.JSONDecodeError:
                args = None
            tool_calls.append(ToolCall(slot["id"], slot["name"], args, slot["arguments"]))

        text = "".join(text_parts)
        assistant: dict[str, Any] = {"role": "assistant", "content": text or None}
        if tool_calls:
            assistant["tool_calls"] = [
                {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.raw_arguments or "{}"}}
                for c in tool_calls
            ]
        stop = "max_tokens" if finish == "length" else ("tool_use" if tool_calls else "end")
        return Turn(assistant_message=assistant, text=text, tool_calls=tool_calls, stop=stop)

    def user_message(self, text: str) -> dict[str, Any]:
        return {"role": "user", "content": text}

    def tool_result_messages(self, outcomes):
        return [
            {"role": "tool", "tool_call_id": o.call.id, "content": o.content}
            for o in outcomes
        ]

    def visible(self, message):
        if message["role"] == "tool":
            return None
        calls = [
            {"name": c["function"]["name"], "arguments": _loads_or_raw(c["function"]["arguments"])}
            for c in message.get("tool_calls") or []
        ]
        return {"role": message["role"], "text": message.get("content") or "", "tool_calls": calls}


def _groq_error(status: int, detail: str) -> str:
    if status == 401:
        return "Groq rejected the API key (check GROQ_API_KEY)."
    if status == 429:
        return "Groq is rate-limiting requests; try again shortly."
    if "tool_use_failed" in detail:
        return "The model produced an invalid tool call; please rephrase and try again."
    return f"Groq API error {status}."


def _loads_or_raw(raw: str) -> Any:
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return raw


def get_provider(name: str | None = None) -> LLMProvider:
    name = (name or settings.AGENT_PROVIDER).lower()
    model = settings.AGENT_MODEL or None
    if name == "anthropic":
        return AnthropicProvider(model)
    if name == "groq":
        return GroqProvider(model)
    raise ProviderError(f"Unknown AGENT_PROVIDER {name!r} (use 'groq' or 'anthropic').")
