"""Activity worker: turns fresh data into things a user sees.

Every few minutes: new-match and deadline notifications. Once a day: due
missions and the weekly digest. All jobs are idempotent (notifications are
deduplicated per user), so running two workers or restarting is harmless.
"""

from __future__ import annotations

import asyncio
import logging

from app.db import SessionLocal
from app.services.digest import send_due_digests
from app.services.missions import run_due_missions
from app.services.notify import notify_deadlines, notify_new_matches

logger = logging.getLogger("workers.activity")

ACTIVITY_INTERVAL_SECONDS = 10 * 60


def run_activity_cycle() -> dict:
    db = SessionLocal()
    try:
        result = {
            "matches": notify_new_matches(db),
            "deadlines": notify_deadlines(db),
            "mission_matches": run_due_missions(db),
            "digests": send_due_digests(db),
        }
    finally:
        db.close()
    if any(result.values()):
        logger.info("Activity cycle: %s", result)
    return result


async def activity_loop() -> None:
    logger.info("Activity worker started (interval=%ds)", ACTIVITY_INTERVAL_SECONDS)
    await asyncio.sleep(30)  # let the embedding worker catch up first
    while True:
        try:
            await asyncio.to_thread(run_activity_cycle)
        except Exception:
            logger.exception("Activity cycle failed")
        await asyncio.sleep(ACTIVITY_INTERVAL_SECONDS)
