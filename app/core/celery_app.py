import os
from datetime import timedelta

from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL")

if not REDIS_URL:
    raise ValueError("REDIS_URL is not configured")

scan_interval_minutes = int(os.getenv("AGENT_SCAN_INTERVAL_MINUTES", "360"))

celery_app = Celery(
    "talentmap",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "app.tasks.scheduled_tasks",
        "app.tasks.test_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


celery_app.conf.beat_schedule = {
    # Fires every hour on the hour.
    # The task checks each user's digest_hour preference and matches against current UTC hour.
    "hourly-job-digest": {
        "task": "app.tasks.scheduled_tasks.daily_job_digest",
        "schedule": crontab(minute=0),
    },
    # Periodic global scan: fetches jobs from external sources (Adzuna/RemoteOK)
    # and matches against active user resumes.
    "global-job-scan": {
        "task": "app.tasks.scheduled_tasks.run_global_scan_task",
        "schedule": timedelta(minutes=scan_interval_minutes),
    },
    # Periodic worker heartbeat to maintain alive status in Redis
    "worker-heartbeat": {
        "task": "app.tasks.scheduled_tasks.worker_heartbeat_task",
        "schedule": 60.0,
    },
}