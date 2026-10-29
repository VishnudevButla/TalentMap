import os
from datetime import timedelta

from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

load_dotenv()

import ssl

REDIS_URL = os.getenv("REDIS_URL")

if not REDIS_URL:
    raise ValueError("REDIS_URL is not configured")

# Normalize rediss:// URLs (e.g. Upstash) to include ssl_cert_reqs if missing
if "rediss://" in REDIS_URL:
    if "ssl_cert_reqs=" not in REDIS_URL:
        sep = "&" if "?" in REDIS_URL else "?"
        REDIS_URL = f"{REDIS_URL}{sep}ssl_cert_reqs=CERT_REQUIRED"
    elif "ssl_cert_reqs=required" in REDIS_URL:
        REDIS_URL = REDIS_URL.replace("ssl_cert_reqs=required", "ssl_cert_reqs=CERT_REQUIRED")

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

celery_conf = {
    "task_serializer": "json",
    "accept_content": ["json"],
    "result_serializer": "json",
    "timezone": "UTC",
    "enable_utc": True,
}

if "rediss://" in REDIS_URL:
    celery_conf["broker_use_ssl"] = {"ssl_cert_reqs": ssl.CERT_REQUIRED}
    celery_conf["redis_backend_use_ssl"] = {"ssl_cert_reqs": ssl.CERT_REQUIRED}

celery_app.conf.update(celery_conf)


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