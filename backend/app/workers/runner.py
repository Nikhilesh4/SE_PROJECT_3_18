"""One place that knows which background workers exist.

Used by the API's lifespan (when RUN_WORKERS_IN_API=true) and by the
standalone worker process (`python -m app.worker_main`).
"""

from __future__ import annotations

import asyncio
import logging

from app.config import settings

logger = logging.getLogger("workers.runner")


def start_workers() -> list[asyncio.Task]:
    from app.workers.activity_worker import activity_loop
    from app.workers.discovery_worker import discovery_loop
    from app.workers.embedding_worker import embedding_loop
    from app.workers.ingestion_worker import ingestion_loop
    from app.workers.rss_refresh_worker import rss_refresh_loop

    loops = [
        ("rss-refresh-worker", rss_refresh_loop),
        ("ingestion-worker", ingestion_loop),
        ("embedding-worker", embedding_loop),
        ("activity-worker", activity_loop),
    ]
    if settings.DISCOVERY_ENABLED:
        loops.append(("discovery-worker", discovery_loop))
    return [asyncio.create_task(fn(), name=name) for name, fn in loops]


async def stop_workers(tasks: list[asyncio.Task]) -> None:
    for task in tasks:
        task.cancel()
    for task in tasks:
        try:
            await task
        except asyncio.CancelledError:
            pass
