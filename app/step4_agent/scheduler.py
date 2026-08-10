"""
app/step4_agent/scheduler.py — AI Job Agent scan cycle + scheduler.

Started from worker.py (a dedicated process, not FastAPI) so the scan
keeps running regardless of whether the API process is up — see
worker.py's module docstring for why. Every function in this file is
plain, framework-agnostic Python — no fastapi import anywhere — so it
works identically whether it's called from worker.py or (as it used to
be) from app/main.py's lifespan.

Fetching (Adzuna/RemoteOK, via job_source_fetcher.run_job_fetch_cycle) is
global and shared — it runs once per interval, not once per user, so N
users don't multiply API quota usage N times. Matching is still
per-user: run_scan_cycle(user_id) scores one user's latest resume against
postings first seen since that user's last scan (matcher.py's incremental
`since` scoping), skipping users with no resume analysis on file
(_get_active_user_ids). get_worker_health() below exposes the scheduler
lock's renewal heartbeat so GET /api/agent/status and the dashboard can
show real process-alive state instead of just a countdown.

start_scheduler() wires three jobs onto an APScheduler AsyncIOScheduler:
  - "global_scan_cycle" (interval): fetch once, then match every registered
    user — and, for users with email_frequency="immediate" (Settings page),
    email them right there via _maybe_send_immediate_email().
  - "daily_digest" (cron): once/day, real per-user Settings
    (email_alerts_enabled, email_frequency, match_threshold — see
    app/services/settings_data.py) decide who actually gets emailed and
    with what cutoff; not an unconditional blast to every user.
  - "scheduler_lock_renew" (interval): keeps this process's claim on the
    single-instance lock alive (see _try_acquire_scheduler_lock below).
"""

import asyncio
import logging
import socket
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from app.core.db import (
    analysis_collection,
    job_postings_collection,
    job_matches_collection,
    user_collection,
    scheduler_locks_collection,
    to_object_id,
)
from app.config import settings
from app.step4_agent import state as agent_state
from app.step4_agent.job_source_fetcher import run_job_fetch_cycle
from app.step4_agent.matcher import run_matching_for_user
from app.step4_agent.email_alerts import send_match_alert_email, MAX_DIGEST_MATCHES
from app.services.activity_log import log_activity
from app.services.settings_data import get_user_notification_prefs

logger = logging.getLogger(__name__)


def _maybe_send_immediate_email(user_id: str, new_matches: list) -> None:
    """
    "immediate" email_frequency means "as soon as a scan finds something,"
    not "the daily digest" — this is that path, called from run_scan_cycle
    right after real matches are found, using the same email template and
    provider chain as the daily digest (send_match_alert_email). Users on
    "daily"/"weekly"/"never" are handled by send_daily_digest instead, so
    this is a no-op for them — nobody gets emailed twice for one match.
    """
    if not new_matches:
        return

    prefs = get_user_notification_prefs(user_id)
    if not prefs["email_alerts_enabled"] or prefs["email_frequency"] != "immediate":
        return

    qualifying = sorted(
        (m for m in new_matches if m["match_score"] >= prefs["match_threshold"]),
        key=lambda m: m["match_score"], reverse=True,
    )
    if not qualifying:
        return

    user_doc = user_collection.find_one({"_id": to_object_id(user_id)})
    to_email = user_doc.get("email") if user_doc else None
    if not to_email:
        return

    if send_match_alert_email(to_email, qualifying):
        agent_state.record_digest_sent(user_id)


async def run_scan_cycle(user_id: str) -> Dict[str, Any]:
    """
    Matches one user's latest resume against the shared job pool. Does not
    fetch — that's run_global_scan_cycle()'s job. Scoped incrementally to
    postings first seen since this user's last scan (see matcher.py's
    `since` param) — a brand-new user (last_scan_at=None) still gets one
    full pass.
    """
    logger.info("Scheduler execution started: user_id=%s", user_id)

    previous_state = agent_state.ensure_agent_state(user_id)
    since = previous_state.get("last_scan_at")

    try:
        new_matches = run_matching_for_user(user_id, since=since)
        jobs_in_pool = job_postings_collection.count_documents({})

        updated_state = agent_state.advance_scan_clock(user_id, status="ok")

        log_activity(
            user_id=user_id,
            type="agent_scan",
            message=f"Agent scan complete — {jobs_in_pool} jobs in pool, {len(new_matches)} new matches",
            icon="briefcase",
            meta={"jobs_scanned": jobs_in_pool, "new_matches": len(new_matches)},
        )

        try:
            _maybe_send_immediate_email(user_id, new_matches)
        except Exception:
            # An email failure shouldn't fail the whole scan cycle for
            # this user — the next cycle (or the daily digest, if they
            # switch frequency) will pick up any matches this missed.
            logger.exception("Immediate email send failed: user_id=%s", user_id)

        logger.info(
            "Scheduler execution completed: user_id=%s jobs_in_pool=%d new_matches=%d",
            user_id, jobs_in_pool, len(new_matches),
        )
        return {**updated_state, "new_matches": len(new_matches)}

    except Exception as exc:  # keep the agent resilient — one bad scan shouldn't wedge the state
        logger.exception("Scheduler execution failed: user_id=%s", user_id)
        updated_state = agent_state.advance_scan_clock(user_id, status="error", last_error=str(exc))
        return {**updated_state, "new_matches": 0}


def _get_active_user_ids() -> set:
    """
    "Active" = has at least one resume analysis on file. Not a new policy —
    run_matching_for_user already no-ops immediately for a user with zero
    analyses (nothing to embed or score against), so this just skips the
    agent_state/activity_log writes and matcher call for accounts that
    signed up and never uploaded a resume, rather than a real engagement
    threshold.
    """
    return set(analysis_collection.distinct("user_id"))


async def run_global_scan_cycle() -> Dict[str, Any]:
    """
    The interval job: one shared fetch, then one match pass per active
    registered user — every user with an analysis on file, no per-user
    opt-in/opt-out.
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

    active_user_ids = _get_active_user_ids()
    user_ids = [
        str(doc["_id"]) for doc in user_collection.find({}, {"_id": 1})
        if str(doc["_id"]) in active_user_ids
    ]
    total_new_matches = 0
    for user_id in user_ids:
        result = await run_scan_cycle(user_id)
        total_new_matches += result.get("new_matches", 0)

    agent_state.record_global_scan(fetch_summary, users_matched=len(user_ids), total_new_matches=total_new_matches)

    logger.info(
        "Global scan cycle completed: fetched=%d saved=%d users_scanned=%d total_new_matches=%d",
        fetch_summary.get("fetched", 0), fetch_summary.get("saved", 0), len(user_ids), total_new_matches,
    )
    return {"fetch": fetch_summary, "users_scanned": len(user_ids), "total_new_matches": total_new_matches}


_WEEKLY_DIGEST_MIN_GAP = timedelta(days=7)


async def send_daily_digest() -> None:
    """
    The cron job: runs once/day, but doesn't unconditionally email every
    user — each user's real Settings preferences (app/routers/settings_api.py,
    stored in user_settings_collection) actually gate this now:
      - email_alerts_enabled=False → skipped entirely.
      - email_frequency="never"    → skipped entirely.
      - email_frequency="immediate" → skipped here — handled instantly by
        _maybe_send_immediate_email() inside run_scan_cycle instead, so
        they're never emailed twice for the same match.
      - email_frequency="daily"   → sent every run (this cron already only
        fires once/day, at settings.email_digest_hour UTC).
      - email_frequency="weekly"  → only sent if _WEEKLY_DIGEST_MIN_GAP has
        actually elapsed since agent_state's last_digest_sent_at.
    match_threshold (also per-user, default 70) replaces what used to be a
    hardcoded status filter — "worth emailing about" is now whatever score
    each user actually configured, not a fixed cutoff for everyone.
    """
    logger.info("Daily digest job started")
    sent = 0

    active_user_ids = _get_active_user_ids()
    for user_doc in user_collection.find({}):
        user_id = str(user_doc["_id"])
        if user_id not in active_user_ids:
            continue
        to_email = user_doc.get("email")
        if not to_email:
            continue

        prefs = get_user_notification_prefs(user_id)
        if not prefs["email_alerts_enabled"] or prefs["email_frequency"] in ("never", "immediate"):
            continue

        if prefs["email_frequency"] == "weekly":
            last_sent = agent_state.ensure_agent_state(user_id).get("last_digest_sent_at")
            if last_sent and (datetime.utcnow() - last_sent) < _WEEKLY_DIGEST_MIN_GAP:
                continue

        top_matches = list(
            job_matches_collection.find(
                {"user_id": user_id, "match_score": {"$gte": prefs["match_threshold"]}}
            ).sort("match_score", -1).limit(MAX_DIGEST_MATCHES)
        )
        if not top_matches:
            continue

        if send_match_alert_email(to_email, top_matches):
            sent += 1
            agent_state.record_digest_sent(user_id)

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
    # upsert=True matters: without it, a renewal that lands after the lock
    # doc has already been deleted (TTL expiry from a single missed
    # renewal — e.g. a scan cycle's synchronous matching call blocking the
    # event loop past APScheduler's default 1s misfire grace) silently
    # matches zero documents forever after. update_one() doesn't raise on
    # that, so every future renewal keeps logging "executed successfully"
    # while doing nothing — get_worker_health() then reports "down"
    # permanently even though this process is alive and working correctly.
    # Caught only by comparing worker.py's own logs against a direct query
    # of scheduler_locks_collection, not by reading this function alone.
    scheduler_locks_collection.update_one(
        {"_id": _LOCK_ID, "holder": _INSTANCE_ID},
        {"$set": {"claimed_at": datetime.utcnow()}},
        upsert=True,
    )


def get_worker_health() -> Dict[str, Any]:
    """
    Reads the lock renewal above as a heartbeat — no separate write path
    needed. Because the lock doc has a TTL of _LOCK_TTL_SECONDS from its
    last claimed_at, Mongo itself deletes it once a holder stops renewing
    it, so a missing doc cleanly means "down" (never started, or crashed
    long enough ago that it already expired) with no extra bookkeeping.
    """
    doc = scheduler_locks_collection.find_one({"_id": _LOCK_ID})
    if not doc:
        return {
            "status": "down",
            "holder": None,
            "last_heartbeat_at": None,
            "seconds_since_heartbeat": None,
        }

    age_seconds = (datetime.utcnow() - doc["claimed_at"]).total_seconds()
    status = "healthy" if age_seconds < _LOCK_RENEW_SECONDS * 2 else "stale"
    return {
        "status": status,
        "holder": doc.get("holder"),
        "last_heartbeat_at": doc["claimed_at"],
        "seconds_since_heartbeat": int(age_seconds),
    }


def start_scheduler() -> None:
    """
    Starts the background AI Job Agent scheduler. Called from worker.py —
    a dedicated process, independent of the FastAPI app — so the scan
    keeps running regardless of whether the API process is up. No-op
    unless agent_scheduler_enabled=true in .env, and only actually starts
    jobs on the one process that wins the lock below (guards against
    accidentally running more than one worker instance at once).
    """
    if not settings.agent_scheduler_enabled:
        logger.info(
            "AI Job Agent scheduler disabled (agent_scheduler_enabled=False) — "
            "no scans will run until it's turned on in .env."
        )
        return

    if not _try_acquire_scheduler_lock():
        logger.info("AI Job Agent scheduler not started on this process — lock held by another instance")
        return

    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    # APScheduler's job store is in-memory only — a process restart would
    # normally recompute "next run = now + interval" from scratch, silently
    # discarding however much of the previous countdown had already
    # elapsed. Resume from the durable agent_global_state.next_scan_at
    # instead, so a restart (dev --reload, a crash, a redeploy) picks the
    # countdown back up rather than restarting the whole 6-hour window.
    # Scheduler runs in explicit UTC to match the naive-UTC timestamps
    # already stored everywhere else in this codebase (mixing naive/aware
    # datetimes here previously caused a real misfire bug).
    global_state = agent_state.get_global_agent_state()
    stored_next_scan_at = global_state.get("next_scan_at")
    first_run_kwargs = {}
    if stored_next_scan_at:
        first_run = stored_next_scan_at.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if first_run < now:
            # Overdue — the process was down past the scheduled time, so
            # fire the catch-up scan right away instead of waiting out a
            # fresh 6-hour window.
            first_run = now
        first_run_kwargs["next_run_time"] = first_run

    scheduler = AsyncIOScheduler(timezone=timezone.utc)
    scheduler.add_job(
        run_global_scan_cycle, "interval",
        minutes=settings.agent_scan_interval_minutes,
        id="global_scan_cycle",
        **first_run_kwargs,
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
