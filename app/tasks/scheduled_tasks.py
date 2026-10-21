"""
app/tasks/scheduled_tasks.py — Celery tasks for background agent scanning and email digests.

Driven by Celery Beat and executed by Celery workers via Redis.
"""

import logging
from datetime import datetime, timezone

from app.core.celery_app import celery_app
from app.step4_agent.scheduler import (
    run_global_scan_cycle,
    record_worker_heartbeat,
)

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.scheduled_tasks.run_global_scan_task", bind=True)
def run_global_scan_task(self):
    """
    Celery Beat task: periodically fetches job listings from external sources
    (Adzuna, RemoteOK) and runs matching against active resumes in MongoDB.
    """
    logger.info("Celery task [run_global_scan_task] started")
    try:
        result = run_global_scan_cycle()
        logger.info("Celery task [run_global_scan_task] completed successfully: %s", result)
        return {"status": "success", "result": result}
    except Exception as exc:
        logger.exception("Celery task [run_global_scan_task] failed: %s", exc)
        return {"status": "error", "error": str(exc)}


@celery_app.task(name="app.tasks.scheduled_tasks.daily_job_digest", bind=True)
def daily_job_digest(self):
    """
    Hourly sweep: email every user whose digest_hour matches now (UTC)
    and who has email alerts enabled and qualifying matches.
    """
    from app.core.db import (
        user_collection,
        user_settings_collection,
        job_matches_collection,
        agent_state_collection,
    )
    from app.step4_agent.email_alerts import send_match_alert_email

    current_hour = datetime.now(timezone.utc).hour
    logger.info("Daily digest sweep started: utc_hour=%d", current_hour)

    sent = 0
    skipped = 0

    for user_doc in user_collection.find({}, {"_id": 1, "email": 1}):
        user_id = str(user_doc["_id"])
        to_email = user_doc.get("email")
        if not to_email:
            skipped += 1
            continue

        # Read this user's notification preferences
        prefs = user_settings_collection.find_one({"user_id": user_id})
        if not prefs:
            skipped += 1
            continue

        notifications = prefs.get("notifications", {})
        if not notifications.get("email_alerts_enabled", False):
            skipped += 1
            continue

        # Check frequency setting
        freq = notifications.get("email_frequency", "daily")
        if freq in ("never", "immediate"):
            skipped += 1
            continue

        # Check if this is the user's preferred send hour
        user_digest_hour = notifications.get("digest_hour", 9)
        if user_digest_hour != current_hour:
            skipped += 1
            continue

        min_score = notifications.get("match_threshold", 70)

        # Fetch top 10 matches meeting the threshold
        top_matches = list(
            job_matches_collection.find(
                {"user_id": user_id, "match_score": {"$gte": min_score}}
            ).sort("match_score", -1).limit(10)
        )
        if not top_matches:
            logger.debug("No qualifying matches for user_id=%s — skipping", user_id)
            skipped += 1
            continue

        if send_match_alert_email(to_email, top_matches):
            sent += 1
            agent_state_collection.update_one(
                {"user_id": user_id},
                {"$inc": {"emails_sent_today": 1}, "$set": {"last_digest_sent_at": datetime.utcnow()}},
                upsert=True,
            )
            logger.info(
                "Digest sent: user_id=%s matches=%d", user_id, len(top_matches)
            )
        else:
            logger.warning("Digest failed to send for user_id=%s", user_id)

    record_worker_heartbeat("daily_job_digest")
    logger.info(
        "Daily digest sweep complete: sent=%d skipped=%d utc_hour=%d",
        sent, skipped, current_hour,
    )
    return {"sent": sent, "skipped": skipped, "utc_hour": current_hour}


@celery_app.task(name="app.tasks.scheduled_tasks.worker_heartbeat_task", bind=True)
def worker_heartbeat_task(self):
    """
    Celery Beat task: periodically updates the Redis worker heartbeat key.
    """
    record_worker_heartbeat("celery_beat")
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}