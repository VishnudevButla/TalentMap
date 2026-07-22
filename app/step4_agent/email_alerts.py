"""
app/step4_agent/email_alerts.py — Job Match Email Alerts

TODO(you): wire real sending. This function is always safely callable —
it no-ops (returns False, logs to console) until settings.email_enabled is
True and SMTP/SES credentials are set in .env, so nothing else in the app
needs to change once you implement it.

Two ways to send, both already available without new dependencies:
  - stdlib smtplib, using settings.smtp_host/port/username/password/from_address
  - AWS SES via boto3 (already a project dependency for S3), using
    settings.ses_region and boto3.client("ses")
"""

import logging
from typing import Any, Dict, List

from app.config import settings

logger = logging.getLogger(__name__)


def send_match_alert_email(to_email: str, matches: List[Dict[str, Any]]) -> bool:
    # Never log `to_email` — it's PII, same rule as everywhere else in the app.
    if not settings.email_enabled:
        logger.debug("Email sending disabled — skipping alert (%d matches)", len(matches))
        return False

    # TODO(you): build the email body from `matches` and send via smtplib or
    # boto3 SES using the settings.smtp_*/ses_region config above.
    logger.warning("email_enabled=True but sending is not implemented yet — skipping alert")
    return False
