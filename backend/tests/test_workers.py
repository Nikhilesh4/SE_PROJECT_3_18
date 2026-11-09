import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.workers import runner

pytestmark = pytest.mark.anyio


async def _forever():
    await asyncio.sleep(3600)


@pytest.fixture
def fake_loops(monkeypatch):
    """Replace every worker loop with a task that just sleeps (no network, no model)."""
    import app.workers.activity_worker as a, app.workers.discovery_worker as d, app.workers.embedding_worker as e
    import app.workers.ingestion_worker as i, app.workers.rss_refresh_worker as r
    for mod, name in ((a, "activity_loop"), (d, "discovery_loop"), (e, "embedding_loop"), (i, "ingestion_loop"), (r, "rss_refresh_loop")):
        monkeypatch.setattr(mod, name, _forever)


async def test_runner_starts_every_worker_and_stops_quickly(fake_loops):
    tasks = runner.start_workers()
    assert {t.get_name() for t in tasks} == {"rss-refresh-worker", "ingestion-worker", "embedding-worker", "activity-worker", "discovery-worker"}
    started = time.monotonic()
    await runner.stop_workers(tasks)
    assert all(t.cancelled() for t in tasks) and time.monotonic() - started < 1


async def test_discovery_worker_can_be_disabled(fake_loops, monkeypatch):
    monkeypatch.setattr(settings, "DISCOVERY_ENABLED", False)
    tasks = runner.start_workers()
    assert "discovery-worker" not in {t.get_name() for t in tasks}
    await runner.stop_workers(tasks)


def test_api_starts_no_workers_when_split_out(fake_loops, monkeypatch, db):
    from app.main import app
    started = []
    monkeypatch.setattr("app.main.start_workers", lambda: started.append(1) or [])
    monkeypatch.setattr(settings, "RUN_WORKERS_IN_API", False)
    with TestClient(app):
        pass
    assert started == []
    monkeypatch.setattr(settings, "RUN_WORKERS_IN_API", True)
    with TestClient(app):
        pass
    assert started == [1]
