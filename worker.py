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

    # On Windows, Click disallows passing '--beat' to 'celery worker'.
    # We start Beat in a dedicated daemon thread and run the solo worker on the main thread.
    if sys.platform.startswith("win"):
        import threading

        def _run_beat():
            try:
                beat = celery_app.Beat(loglevel="info")
                beat.run()
            except Exception as e:
                logger.error("Celery Beat encountered an error: %s", e)

        beat_thread = threading.Thread(target=_run_beat, daemon=True, name="celery-beat")
        beat_thread.start()
        logger.info("Celery Beat scheduler running in background thread.")

        argv = ["worker", "--loglevel=info", "-P", "solo"]
    else:
        argv = ["worker", "--beat", "--loglevel=info"]

    try:
        celery_app.worker_main(argv)
    except KeyboardInterrupt:
        logger.info("TalentMap worker stopped.")


if __name__ == "__main__":
    main()
