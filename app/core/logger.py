"""
app/core/logger.py — centralized logging configuration.

Call setup_logging() exactly once, at application startup (app/main.py),
before any other app module is imported. Every other module then just
does:

    import logging
    logger = logging.getLogger(__name__)

and logs normally — the module-qualified name (e.g. "app.core.db",
"app.step4_agent.scheduler") comes from __name__ automatically and shows
up in every formatted line, so there's no logger instance to pass around.
"""

import logging
import logging.handlers
import sys
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_FILE = LOG_DIR / "app.log"

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"

# Third-party loggers that are noisy at INFO/DEBUG and would drown out our
# own log lines if left at their default level.
_NOISY_LOGGERS = (
    "pymongo", "botocore", "boto3", "urllib3",
    "sentence_transformers", "httpx", "httpcore", "huggingface_hub", "filelock",
)

_configured = False


def setup_logging() -> None:
    global _configured
    if _configured:
        return

    from app.config import settings  # local import: avoids a circular import at module load time

    level = getattr(logging, str(getattr(settings, "log_level", "INFO")).upper(), logging.INFO)

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(_FORMAT, datefmt=_DATEFMT)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(console_handler)
    root.addHandler(file_handler)

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    _configured = True
