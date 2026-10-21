"""
worker.py — AI Job Agent background worker using Celery + Redis.

Runs Celery Worker with Celery Beat to execute periodic job fetching,
resume matching scans, and email digests.

Run as:
    python worker.py
Or directly via Celery CLI:
    celery -A app.core.celery_app worker --beat --loglevel=info -P solo
"""

import sys
import logging

from app.core.logger import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

from app.core.celery_app import celery_app


def main() -> None:
    logger.info("Starting TalentMap Celery Worker with Beat scheduler on Redis...")
    argv = ["worker", "--beat", "--loglevel=info"]
    # On Windows, multiprocessing pool requires solo or threads
    if sys.platform.startswith("win"):
        argv.extend(["-P", "solo"])

    try:
        celery_app.worker_main(argv)
    except KeyboardInterrupt:
        logger.info("TalentMap worker stopped.")


if __name__ == "__main__":
    main()
