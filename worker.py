"""
worker.py — AI Job Agent background worker. Run as: python worker.py

A dedicated process, entirely separate from the FastAPI app (app/main.py).
This exists because the scheduler previously only ran while `uvicorn` was
alive — close the terminal, and nothing scanned, matched, or emailed until
it was started again. Splitting it into its own process means the scan
keeps running on whatever machine hosts this file, independent of the API
process's lifecycle.

FastAPI and this worker never talk to each other directly — they only
share MongoDB. Every status endpoint (GET /api/agent/status, the
dashboard's AI Job Agent panel) already reads scan state from the
agent_global_state/agent_state collections rather than any in-memory
object, so it doesn't matter which process (or whether this one is even
running right now) wrote that state.

No Celery/Redis/RabbitMQ — this is the same APScheduler-based
app.step4_agent.scheduler code that used to run inside FastAPI's
lifespan, just started here instead. See app/step4_agent/scheduler.py
for the actual scan/match/email logic and its Mongo-based leader lock
(makes it safe to accidentally run more than one worker instance at once,
e.g. briefly during a redeploy — only one will actually do the work).
"""

import asyncio
import logging

# Logging must be configured before any app.* module is imported — same
# ordering requirement app/main.py follows, since app.core.db connects to
# MongoDB at import time.
from app.core.logger import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

from app.config import settings
from app.step4_agent.scheduler import start_scheduler

# How long to sleep between wakeups while idling — just keeps the process
# alive so APScheduler's own event-loop-driven jobs can fire; the actual
# scan cadence is controlled by settings.agent_scan_interval_minutes.
_IDLE_SLEEP_SECONDS = 3600


async def _run_forever() -> None:
    logger.info("TalentMap worker starting up")
    start_scheduler()
    try:
        while True:
            await asyncio.sleep(_IDLE_SLEEP_SECONDS)
    finally:
        logger.info("TalentMap worker shutting down")


def main() -> None:
    if not settings.agent_scheduler_enabled:
        logger.info(
            "agent_scheduler_enabled=False in .env — nothing to do. "
            "Turn it on and restart this process when you're ready to scan."
        )
        return

    try:
        asyncio.run(_run_forever())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
