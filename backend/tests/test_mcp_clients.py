import json
import sys
from contextlib import AsyncExitStack
from pathlib import Path

import pytest

from app.services.agent.mcp_clients import ExternalTools, ServerConfig, load_config, tool_allowed

FAKE = str(Path(__file__).parent / "fixtures" / "fake_external_mcp.py")
pytestmark = pytest.mark.anyio


def _cfg(**kw) -> ServerConfig:
    base = dict(name="gcal", command=sys.executable, args=["-I", FAKE], enabled=True)
    base.update(kw)
    return ServerConfig(**base)


def test_allow_rules():
    cfg = ServerConfig(name="x", allow=["list_events"], allow_write=["create_event"])
    assert tool_allowed(cfg, "list_events") and tool_allowed(cfg, "create_event")
    assert not tool_allowed(cfg, "send_email") and not tool_allowed(cfg, "get_thing")  # not in allow
    open_cfg = ServerConfig(name="y")
    assert tool_allowed(open_cfg, "get_thing") and not tool_allowed(open_cfg, "delete_event") and not tool_allowed(open_cfg, "post_message")


def test_config_loading(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"servers": [{"name": "ok", "command": "x", "enabled": True}, {"name": "Bad Name!"}, {"name": "off"}]}))
    cfgs = load_config(p)
    assert [c.name for c in cfgs] == ["ok", "off"] and cfgs[0].enabled and not cfgs[1].enabled
    assert load_config(tmp_path / "missing.json") == []
    (tmp_path / "broken.json").write_text("{nope")
    assert load_config(tmp_path / "broken.json") == []


def test_shipped_config_is_valid_and_fully_disabled():
    cfgs = load_config()
    assert cfgs and all(not c.enabled for c in cfgs)


async def test_external_server_tools_are_filtered_namespaced_and_callable():
    ext = ExternalTools([_cfg(allow_write=["create_event"])])
    async with AsyncExitStack() as stack:
        await ext.start(stack)
        names = {s.name for s in ext.specs}
        assert names == {"gcal__list_events", "gcal__create_event"}        # send_email / delete_event withheld
        assert all(s.description.startswith("[external: gcal]") for s in ext.specs)
        assert ext.owns("gcal__list_events") and not ext.owns("search_opportunities")
        assert await ext.call("gcal__list_events", {"day": "Mon"}) == ("events on Mon: standup", False)
        text, is_error = await ext.call("gcal__send_email", {"to": "a@b.c"})      # guessing a withheld tool name
        assert is_error and "not permitted" in text


async def test_disabled_missing_env_and_broken_servers_are_skipped(monkeypatch):
    monkeypatch.delenv("NEEDED_TOKEN", raising=False)
    ext = ExternalTools([
        _cfg(name="off", enabled=False),
        _cfg(name="noenv", requires_env=["NEEDED_TOKEN"]),
        ServerConfig(name="broken", command="/nonexistent/binary", enabled=True),
        _cfg(name="good"),
    ])
    async with AsyncExitStack() as stack:
        await ext.start(stack)
        assert {s.name.split("__")[0] for s in ext.specs} == {"good"}
        assert ext.skipped["noenv"].startswith("missing env") and ext.skipped["broken"].startswith("failed to start")
        assert "off" not in ext.skipped
