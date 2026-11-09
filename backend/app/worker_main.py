"""Standalone worker process: `python -m app.worker_main`.

Runs the same background loops the API can host, but in their own process so a
slow feed fetch or embedding batch can never delay an API request, and the API
shuts down instantly. Set RUN_WORKERS_IN_API=false on the API when using this.
"""

from __future__ import annotations

import asyncio
import logging
import signal

from app.config import settings
from app.migrations import run_migrations
from app.workers.runner import start_workers, stop_workers


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if settings.RUN_MIGRATIONS_ON_STARTUP:
        await asyncio.to_thread(run_migrations)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    tasks = start_workers()
    logging.getLogger("worker").info("Started %d workers", len(tasks))
    await stop.wait()
    await stop_workers(tasks)


if __name__ == "__main__":
    asyncio.run(main())
