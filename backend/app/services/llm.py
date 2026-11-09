"""One-shot LLM completions for background agents (extraction, drafting, digests).

Everything built on this has a non-LLM fallback: `complete` returns None when no
model is configured or the call fails, and callers must cope. Untrusted text
(posting pages, search snippets) goes in the *prompt* inside delimiters and the
system prompt tells the model to treat it as data.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable

from app.services.agent.providers import LLMProvider, ProviderError, get_provider

logger = logging.getLogger("llm")

# Tests (and alternative deployments) can replace this.
provider_factory: Callable[[], LLMProvider] = get_provider


async def complete(system: str, prompt: str) -> str | None:
    try:
        provider = provider_factory()
    except Exception as exc:  # missing API key etc.
        logger.info("No LLM available: %s", exc)
        return None

    async def ignore(_: str) -> None:
        return None

    try:
        turn = await provider.stream_turn(system=system, history=[provider.user_message(prompt)], tools=[], on_text=ignore)
    except (ProviderError, Exception) as exc:  # noqa: BLE001 — fallbacks exist for every caller
        logger.warning("LLM call failed: %s", exc)
        return None
    text = (turn.text or "").strip()
    return text or None


def complete_sync(system: str, prompt: str) -> str | None:
    """For worker threads (no running event loop)."""
    return asyncio.run(complete(system, prompt))
