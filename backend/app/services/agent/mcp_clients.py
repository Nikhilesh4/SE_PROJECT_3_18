"""External MCP servers the Compass Agent can use (Calendar, Gmail, GitHub, Notion, Playwright …).

Configured in `mcp_clients.json` (path: MCP_CLIENTS_PATH). Each entry:

    {"name": "gcal", "enabled": true, "command": "npx", "args": ["-y", "some-calendar-mcp"],
     "env": {"GOOGLE_TOKEN": "${GOOGLE_TOKEN}"}, "requires_env": ["GOOGLE_TOKEN"],
     "allow": ["list_events"], "allow_write": ["create_event"]}

or {"url": "https://.../mcp"} instead of command/args for a remote server.

Safety rules, enforced here rather than left to the model:
* Servers ship **disabled**; one whose `requires_env` variables are missing is skipped, not an error.
* A server that fails to start or list tools is skipped; the rest of the agent keeps working.
* Tools whose names look like they send, delete or publish (send, delete, trash, post, publish, remove,
  archive, transfer, pay …) are NOT exposed unless the operator lists them in `allow_write`.
  The agent drafts; the student sends.
* Tools are namespaced `<server>__<tool>`, so an external tool can never shadow a built-in one.
* Results are clipped and the system prompt marks everything external as untrusted data.
"""

from __future__ import annotations

import json
import logging
import os
import re
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from app.config import settings
from app.services.agent.providers import ToolSpec

logger = logging.getLogger("agent.mcp_clients")

DEFAULT_PATH = Path(__file__).with_name("mcp_clients.json")
SEPARATOR = "__"
SENSITIVE = re.compile(r"(send|delete|trash|remove|post|publish|archive|transfer|pay|purchase|submit|reply|forward|drop|truncate|execute|upload)", re.I)
_VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


@dataclass
class ServerConfig:
    name: str
    command: str | None = None
    args: list[str] = field(default_factory=list)
    url: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    requires_env: list[str] = field(default_factory=list)
    allow: list[str] | None = None        # None = every non-sensitive tool
    allow_write: list[str] = field(default_factory=list)
    enabled: bool = False


def _expand(value: str) -> str:
    return _VAR.sub(lambda m: os.environ.get(m.group(1), ""), value)


def load_config(path: str | Path | None = None) -> list[ServerConfig]:
    p = Path(path or getattr(settings, "MCP_CLIENTS_PATH", "") or DEFAULT_PATH)
    try:
        raw = json.loads(p.read_text())
    except FileNotFoundError:
        return []
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Cannot read MCP client config %s: %s", p, exc)
        return []
    out = []
    for entry in raw.get("servers", []) if isinstance(raw, dict) else []:
        if not isinstance(entry, dict) or not re.fullmatch(r"[a-z][a-z0-9-]{0,23}", str(entry.get("name", ""))):
            logger.warning("Ignoring MCP client entry without a valid name: %r", entry)
            continue
        out.append(ServerConfig(
            name=entry["name"], command=entry.get("command"), args=list(entry.get("args", [])), url=entry.get("url"),
            env={k: str(v) for k, v in (entry.get("env") or {}).items()}, requires_env=list(entry.get("requires_env", [])),
            allow=entry.get("allow"), allow_write=list(entry.get("allow_write", [])), enabled=bool(entry.get("enabled", False)),
        ))
    return out


def tool_allowed(cfg: ServerConfig, tool: str) -> bool:
    if tool in cfg.allow_write:
        return True
    if SENSITIVE.search(tool):
        return False
    return cfg.allow is None or tool in cfg.allow


class ExternalTools:
    """Connects to every usable configured server and exposes their (filtered) tools."""

    def __init__(self, configs: list[ServerConfig] | None = None) -> None:
        self._configs = load_config() if configs is None else configs
        self._clients: dict[str, Client] = {}
        self.specs: list[ToolSpec] = []
        self.skipped: dict[str, str] = {}

    async def start(self, stack: AsyncExitStack) -> None:
        for cfg in self._configs:
            if not cfg.enabled:
                continue
            missing = [v for v in cfg.requires_env if not os.environ.get(v)]
            if missing:
                self.skipped[cfg.name] = f"missing env: {', '.join(missing)}"
                continue
            try:
                client = await stack.enter_async_context(Client(self._target(cfg)))
                listed = await client.list_tools()
            except Exception as exc:  # noqa: BLE001 — one broken server must not break the assistant
                self.skipped[cfg.name] = f"failed to start: {exc.__class__.__name__}"
                logger.warning("MCP server %s unavailable: %s", cfg.name, exc)
                continue
            self._clients[cfg.name] = client
            for t in listed.tools:
                if tool_allowed(cfg, t.name):
                    self.specs.append(ToolSpec(
                        name=f"{cfg.name}{SEPARATOR}{t.name}",
                        description=f"[external: {cfg.name}] {t.description or ''}",
                        input_schema=t.input_schema,
                    ))
                else:
                    logger.info("MCP %s: tool %s withheld (not allow-listed / sensitive)", cfg.name, t.name)

    @staticmethod
    def _target(cfg: ServerConfig):
        if cfg.url:
            return cfg.url
        env = {k: _expand(v) for k, v in cfg.env.items()}
        return StdioServerParameters(command=cfg.command or "", args=cfg.args, env={**os.environ, **env} if env else None)

    def owns(self, tool_name: str) -> bool:
        return SEPARATOR in tool_name and tool_name.split(SEPARATOR, 1)[0] in self._clients

    async def call(self, tool_name: str, arguments: dict[str, Any]) -> tuple[str, bool]:
        """(text, is_error). Re-checks the allow-list so a model can't call a withheld tool by guessing its name."""
        server, tool = tool_name.split(SEPARATOR, 1)
        cfg = next(c for c in self._configs if c.name == server)
        if not tool_allowed(cfg, tool):
            return f"{tool_name} is not permitted.", True
        result = await self._clients[server].call_tool(tool, arguments)
        text = " ".join(getattr(c, "text", "") for c in result.content).strip()
        return text or "(no output)", bool(result.is_error)
