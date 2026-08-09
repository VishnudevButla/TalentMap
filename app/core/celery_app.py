import os

from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL")

if not REDIS_URL:
    raise ValueError("REDIS_URL is not configured")


celery_app = Celery(
    "talentmap",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "app.tasks.scheduled_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
)


celery_app.conf.beat_schedule = {
    # Fires every hour on the hour (e.g. 09:00, 10:00 UTC).
    # The task itself checks each user's digest_hour preference and only
    # sends to users whose hour matches — so no user gets double-emailed.
    "hourly-job-digest": {
        "task": "app.tasks.scheduled_tasks.daily_job_digest",
        "schedule": crontab(minute=0),
    },
}