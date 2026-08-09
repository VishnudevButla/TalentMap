"""
app/tasks/scheduled_tasks.py — Celery tasks for the daily job digest.

Celery Beat fires daily_job_digest every hour on the hour. The task
sweeps all users, picks only those whose preferred digest_hour matches
the current UTC hour and who have email_alerts_enabled=True, then sends
them their top-10 scored matches.

Job fetching and scoring are handled separately by worker.py / APScheduler
(run_global_scan_cycle). This task only reads already-scored matches from
MongoDB and delivers them — the two concerns are kept separate intentionally.
"""

import logging
from datetime import datetime, timezone

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.scheduled_tasks.daily_job_digest", bind=True)
def daily_job_digest(self):
    """
    Hourly sweep: email every user whose digest_hour matches now (UTC)
    and who has email alerts enabled. Sends their top 10 matches sorted
    by match_score descending (status = excellent or good only).
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

        # Check if this is the user's preferred send hour
        user_digest_hour = notifications.get("digest_hour", 9)
        if user_digest_hour != current_hour:
            skipped += 1
            continue

        # Fetch top 10 matches (best-first, only strong matches)
        top_matches = list(
            job_matches_collection.find(
                {"user_id": user_id, "status": {"$in": ["excellent", "good"]}}
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
                {"$inc": {"emails_sent_today": 1}},
                upsert=True,
            )
            logger.info(
                "Digest sent: user_id=%s matches=%d", user_id, len(top_matches)
            )
        else:
            logger.warning("Digest failed to send for user_id=%s", user_id)

    logger.info(
        "Daily digest sweep complete: sent=%d skipped=%d utc_hour=%d",
        sent, skipped, current_hour,
    )
    return {"sent": sent, "skipped": skipped, "utc_hour": current_hour}