"""
app/step4_agent/scheduler.py — AI Job Agent scan cycle + scheduler.

Fetching (Adzuna/RemoteOK, via job_source_fetcher.run_job_fetch_cycle) is
global and shared — it runs once per interval, not once per user, so N
active users don't multiply API quota usage N times. Matching is still
per-user: run_scan_cycle(user_id) scores one user's latest resume against
whatever is currently in job_postings_collection.

start_scheduler() wires three jobs onto an APScheduler AsyncIOScheduler:
  - "global_scan_cycle" (interval): fetch once, then match every active user.
  - "daily_digest" (cron): once/day, top matches emailed per active user.
  - "scheduler_lock_renew" (interval): keeps this process's claim on the
    single-instance lock alive (see _try_acquire_scheduler_lock below).
"""

import asyncio
import logging
import socket
import uuid
from datetime import datetime
from typing import Any, Dict

from bson import ObjectId

from app.core.db import (
    job_postings_collection,
    job_matches_collection,
    user_collection,
    agent_state_collection,
    scheduler_locks_collection,
)
from app.config import settings
from app.step4_agent import state as agent_state
from app.step4_agent.job_source_fetcher import run_job_fetch_cycle
from app.step4_agent.matcher import run_matching_for_user
from app.step4_agent.email_alerts import send_match_alert_email, MAX_DIGEST_MATCHES
from app.services.activity_log import log_activity

logger = logging.getLogger(__name__)


async def run_scan_cycle(user_id: str) -> Dict[str, Any]:
    """
    Matches one user's latest resume against the shared job pool. Does not
    fetch — that's run_global_scan_cycle()'s job — so this is safe to call
    as often as needed (e.g. manually via POST /api/agent/scan-now)
    without burning any external API quota.
    """
    logger.info("Scheduler execution started: user_id=%s", user_id)

    agent_state.ensure_agent_state(user_id, settings.agent_scan_interval_minutes)

    try:
        new_matches = run_matching_for_user(user_id)
        jobs_scanned = job_postings_collection.count_documents({})

        updated_state = agent_state.advance_scan_clock(
            user_id, jobs_scanned=jobs_scanned, new_matches=len(new_matches), emails_sent=0
        )

        log_activity(
            user_id=user_id,
            type="agent_scan",
            message=f"Agent scan complete — {jobs_scanned} jobs in pool, {len(new_matches)} new matches",
            icon="briefcase",
        )

        logger.info(
            "Scheduler execution completed: user_id=%s jobs_scanned=%d new_matches=%d",
            user_id, jobs_scanned, len(new_matches),
        )
        return updated_state

    except Exception as exc:  # keep the agent resilient — one bad scan shouldn't wedge the state
        logger.exception("Scheduler execution failed: user_id=%s", user_id)
        return agent_state.advance_scan_clock(
            user_id, jobs_scanned=0, new_matches=0, emails_sent=0,
            status="error", last_error=str(exc),
        )


async def run_global_scan_cycle() -> Dict[str, Any]:
    """
    The interval job: one shared fetch, then one match pass per active user.
    """
    logger.info("Global scan cycle started")

    try:
        loop = asyncio.get_running_loop()
        # run_job_fetch_cycle() is blocking (requests + time.sleep) — run it
        # off the event loop so it doesn't stall everything else in the app.
        fetch_summary = await loop.run_in_executor(None, run_job_fetch_cycle)
    except Exception:
        logger.exception("Global fetch step failed — matching will proceed against the existing pool")
        fetch_summary = {"fetched": 0, "saved": 0}

    active_user_ids = [doc["user_id"] for doc in agent_state_collection.find({"is_active": True})]
    for user_id in active_user_ids:
        await run_scan_cycle(user_id)

    logger.info(
        "Global scan cycle completed: fetched=%d saved=%d users_scanned=%d",
        fetch_summary.get("fetched", 0), fetch_summary.get("saved", 0), len(active_user_ids),
    )
    return {"fetch": fetch_summary, "users_scanned": len(active_user_ids)}


async def send_daily_digest() -> None:
    """
    The cron job: once/day, emails each active user their top matches
    (score >= 70 only — a low match is not worth interrupting someone's day
    for). Skips users with no qualifying matches entirely.
    """
    logger.info("Daily digest job started")
    sent = 0

    for state_doc in agent_state_collection.find({"is_active": True}):
        user_id = state_doc["user_id"]

        try:
            user_doc = user_collection.find_one({"_id": ObjectId(user_id)}) or {}
        except Exception:
            logger.warning("Could not look up user for digest email: user_id=%s", user_id)
            continue

        to_email = user_doc.get("email")
        if not to_email:
            continue

        top_matches = list(
            job_matches_collection.find(
                {"user_id": user_id, "status": {"$in": ["excellent", "good"]}}
            ).sort("match_score", -1).limit(MAX_DIGEST_MATCHES)
        )
        if not top_matches:
            continue

        if send_match_alert_email(to_email, top_matches):
            sent += 1
            agent_state_collection.update_one(
                {"user_id": user_id}, {"$inc": {"emails_sent_today": 1}}
            )

    logger.info("Daily digest job completed: emails_sent=%d", sent)


# ---------------------------------------------------------------------------
# Single-instance lock — so only one process's scheduler runs jobs even if
# the app is ever started with multiple worker processes. The lock doc has
# a TTL index (set up on first acquire attempt) so a crashed process's
# claim self-expires instead of blocking the app forever; a live holder
# renews it well before that TTL via the "scheduler_lock_renew" job.
# ---------------------------------------------------------------------------

_LOCK_ID = "ai_job_agent_scheduler"
_LOCK_TTL_SECONDS = 300
_LOCK_RENEW_SECONDS = 120
_INSTANCE_ID = f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"


def _try_acquire_scheduler_lock() -> bool:
    scheduler_locks_collection.create_index("claimed_at", expireAfterSeconds=_LOCK_TTL_SECONDS)

    result = scheduler_locks_collection.update_one(
        {"_id": _LOCK_ID},
        {"$setOnInsert": {"holder": _INSTANCE_ID, "claimed_at": datetime.utcnow()}},
        upsert=True,
    )
    if result.upserted_id is not None:
        return True

    doc = scheduler_locks_collection.find_one({"_id": _LOCK_ID})
    return bool(doc and doc.get("holder") == _INSTANCE_ID)


def _renew_scheduler_lock() -> None:
    scheduler_locks_collection.update_one(
        {"_id": _LOCK_ID, "holder": _INSTANCE_ID},
        {"$set": {"claimed_at": datetime.utcnow()}},
    )


def start_scheduler(app) -> None:
    """
    Starts the background AI Job Agent scheduler. No-op unless
    agent_scheduler_enabled=true in .env, and only actually starts jobs on
    the one process that wins the lock above.
    """
    if not settings.agent_scheduler_enabled:
        logger.info(
            "AI Job Agent scheduler disabled (agent_scheduler_enabled=False) — "
            "use POST /api/agent/scan-now to trigger a manual scan."
        )
        return

    if not _try_acquire_scheduler_lock():
        logger.info("AI Job Agent scheduler not started on this process — lock held by another instance")
        return

    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_global_scan_cycle, "interval",
        minutes=settings.agent_scan_interval_minutes,
        id="global_scan_cycle",
    )
    scheduler.add_job(
        send_daily_digest, "cron",
        hour=settings.email_digest_hour, minute=0,
        id="daily_digest",
    )
    scheduler.add_job(
        _renew_scheduler_lock, "interval",
        seconds=_LOCK_RENEW_SECONDS,
        id="scheduler_lock_renew",
    )
    scheduler.start()

    logger.info(
        "AI Job Agent scheduler started: instance=%s scan_interval_minutes=%d digest_hour=%d",
        _INSTANCE_ID, settings.agent_scan_interval_minutes, settings.email_digest_hour,
    )
