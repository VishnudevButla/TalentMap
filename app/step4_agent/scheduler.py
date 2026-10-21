"""
app/step4_agent/scheduler.py — AI Job Agent scan cycle and execution logic.

Background scheduling and execution are driven by Celery + Celery Beat over Redis.
The functions in this module are plain, framework-agnostic Python functions
responsible for fetching job listings, executing incremental resume matching per user,
and sending digests / immediate alerts.
"""

import logging
import os
import socket
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict

from app.core.db import (
    analysis_collection,
    job_postings_collection,
    job_matches_collection,
    user_collection,
    scheduler_locks_collection,
    to_object_id,
)
from app.step4_agent import state as agent_state
from app.step4_agent.job_source_fetcher import run_job_fetch_cycle
from app.step4_agent.matcher import run_matching_for_user
from app.step4_agent.email_alerts import send_match_alert_email, MAX_DIGEST_MATCHES
from app.services.activity_log import log_activity
from app.services.settings_data import get_user_notification_prefs

logger = logging.getLogger(__name__)

_LOCK_ID = "ai_job_agent_worker"
_INSTANCE_ID = f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
REDIS_HEARTBEAT_KEY = "talentmap:worker:heartbeat"


def _maybe_send_immediate_email(user_id: str, new_matches: list) -> None:
    """
    "immediate" email_frequency means "as soon as a scan finds something,"
    not "the daily digest" — this is that path, called from run_scan_cycle
    right after real matches are found.
    """
    if not new_matches:
        return

    prefs = get_user_notification_prefs(user_id)
    if not prefs["email_alerts_enabled"] or prefs["email_frequency"] != "immediate":
        return

    qualifying = sorted(
        (m for m in new_matches if m["match_score"] >= prefs["match_threshold"]),
        key=lambda m: m["match_score"],
        reverse=True,
    )
    if not qualifying:
        return

    user_doc = user_collection.find_one({"_id": to_object_id(user_id)})
    to_email = user_doc.get("email") if user_doc else None
    if not to_email:
        return

    if send_match_alert_email(to_email, qualifying):
        agent_state.record_digest_sent(user_id)


def run_scan_cycle(user_id: str) -> Dict[str, Any]:
    """
    Matches one user's latest resume against the shared job pool.
    Scoped incrementally to postings first seen since this user's last scan.
    """
    logger.info("Scan cycle execution started: user_id=%s", user_id)

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
            logger.exception("Immediate email send failed: user_id=%s", user_id)

        logger.info(
            "Scan cycle execution completed: user_id=%s jobs_in_pool=%d new_matches=%d",
            user_id,
            jobs_in_pool,
            len(new_matches),
        )
        return {**updated_state, "new_matches": len(new_matches)}

    except Exception as exc:
        logger.exception("Scan cycle execution failed: user_id=%s", user_id)
        updated_state = agent_state.advance_scan_clock(user_id, status="error", last_error=str(exc))
        return {**updated_state, "new_matches": 0}


def _get_active_user_ids() -> set:
    """
    "Active" = has at least one resume analysis on file.
    """
    return set(analysis_collection.distinct("user_id"))


def run_global_scan_cycle() -> Dict[str, Any]:
    """
    Shared fetch step, followed by incremental matching for all active registered users.
    Executed by Celery worker via Redis scheduling.
    """
    logger.info("Global scan cycle started")

    try:
        fetch_summary = run_job_fetch_cycle()
    except Exception:
        logger.exception("Global fetch step failed — matching will proceed against existing pool")
        fetch_summary = {"fetched": 0, "saved": 0}

    active_user_ids = _get_active_user_ids()
    user_ids = [
        str(doc["_id"]) for doc in user_collection.find({}, {"_id": 1})
        if str(doc["_id"]) in active_user_ids
    ]
    total_new_matches = 0
    for user_id in user_ids:
        result = run_scan_cycle(user_id)
        total_new_matches += result.get("new_matches", 0)

    agent_state.record_global_scan(fetch_summary, users_matched=len(user_ids), total_new_matches=total_new_matches)
    record_worker_heartbeat("global_scan_cycle")

    logger.info(
        "Global scan cycle completed: fetched=%d saved=%d users_scanned=%d total_new_matches=%d",
        fetch_summary.get("fetched", 0),
        fetch_summary.get("saved", 0),
        len(user_ids),
        total_new_matches,
    )
    return {"fetch": fetch_summary, "users_scanned": len(user_ids), "total_new_matches": total_new_matches}


_WEEKLY_DIGEST_MIN_GAP = timedelta(days=7)


def send_daily_digest() -> Dict[str, Any]:
    """
    Sweeps active users and delivers email digests according to user preferences:
      - email_alerts_enabled=False -> skip
      - email_frequency in ("never", "immediate") -> skip
      - email_frequency="weekly" -> only send if 7 days elapsed since last
      - match_threshold -> only include matches meeting score threshold
    """
    logger.info("Daily digest job started")
    sent = 0
    skipped = 0

    active_user_ids = _get_active_user_ids()
    for user_doc in user_collection.find({}):
        user_id = str(user_doc["_id"])
        if user_id not in active_user_ids:
            skipped += 1
            continue
        to_email = user_doc.get("email")
        if not to_email:
            skipped += 1
            continue

        prefs = get_user_notification_prefs(user_id)
        if not prefs["email_alerts_enabled"] or prefs["email_frequency"] in ("never", "immediate"):
            skipped += 1
            continue

        if prefs["email_frequency"] == "weekly":
            last_sent = agent_state.ensure_agent_state(user_id).get("last_digest_sent_at")
            if last_sent and (datetime.utcnow() - last_sent) < _WEEKLY_DIGEST_MIN_GAP:
                skipped += 1
                continue

        top_matches = list(
            job_matches_collection.find(
                {"user_id": user_id, "match_score": {"$gte": prefs["match_threshold"]}}
            ).sort("match_score", -1).limit(MAX_DIGEST_MATCHES)
        )
        if not top_matches:
            skipped += 1
            continue

        if send_match_alert_email(to_email, top_matches):
            sent += 1
            agent_state.record_digest_sent(user_id)
        else:
            skipped += 1

    record_worker_heartbeat("daily_digest")
    logger.info("Daily digest job completed: sent=%d skipped=%d", sent, skipped)
    return {"sent": sent, "skipped": skipped}


# ---------------------------------------------------------------------------
# Redis & MongoDB Heartbeat / Health Tracking
# ---------------------------------------------------------------------------

def record_worker_heartbeat(source: str = "celery") -> None:
    """
    Records worker activity into Redis and MongoDB to provide real-time
    health and liveness monitoring for the dashboard.
    """
    now = datetime.utcnow()
    # 1. Update MongoDB lock/heartbeat collection
    try:
        scheduler_locks_collection.update_one(
            {"_id": _LOCK_ID},
            {"$set": {"holder": _INSTANCE_ID, "source": source, "claimed_at": now}},
            upsert=True,
        )
    except Exception:
        logger.debug("Failed to record worker heartbeat in MongoDB", exc_info=True)

    # 2. Update Redis key if available
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        try:
            import redis
            r = redis.from_url(redis_url)
            r.set(REDIS_HEARTBEAT_KEY, now.isoformat(), ex=300)
        except Exception:
            logger.debug("Failed to record worker heartbeat in Redis", exc_info=True)


def get_worker_health() -> Dict[str, Any]:
    """
    Checks Redis and MongoDB heartbeats to determine whether the Celery/Redis
    worker is healthy, stale, or down.
    """
    now = datetime.utcnow()
    last_heartbeat_at = None
    holder = "redis-celery-worker"

    # Check Redis first
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        try:
            import redis
            r = redis.from_url(redis_url, socket_connect_timeout=1)
            raw = r.get(REDIS_HEARTBEAT_KEY)
            if raw:
                last_heartbeat_at = datetime.fromisoformat(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        except Exception:
            pass

    # Fallback to MongoDB
    if not last_heartbeat_at:
        doc = scheduler_locks_collection.find_one({"_id": _LOCK_ID})
        if doc and doc.get("claimed_at"):
            last_heartbeat_at = doc["claimed_at"]
            holder = doc.get("holder", holder)

    if not last_heartbeat_at:
        return {
            "status": "down",
            "holder": None,
            "last_heartbeat_at": None,
            "seconds_since_heartbeat": None,
        }

    age_seconds = (now - last_heartbeat_at).total_seconds()
    if age_seconds < 240:
        status = "healthy"
    elif age_seconds < 600:
        status = "stale"
    else:
        status = "down"

    return {
        "status": status,
        "holder": holder,
        "last_heartbeat_at": last_heartbeat_at,
        "seconds_since_heartbeat": int(age_seconds),
    }


def start_scheduler() -> None:
    """
    Notice helper. Background scheduling is handled exclusively by Celery Beat
    over Redis (e.g. `celery -A app.core.celery_app worker --beat` or `python worker.py`).
    """
    logger.info("Scheduler runs via Celery Beat + Redis.")
