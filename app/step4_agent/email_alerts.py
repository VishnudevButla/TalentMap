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

from typing import Any, Dict, List

from app.config import settings


def send_match_alert_email(to_email: str, matches: List[Dict[str, Any]]) -> bool:
    if not settings.email_enabled:
        print(f"[email_alerts] Email sending disabled — skipping alert to {to_email} ({len(matches)} matches).")
        return False

    # TODO(you): build the email body from `matches` and send via smtplib or
    # boto3 SES using the settings.smtp_*/ses_region config above.
    print(f"[email_alerts] email_enabled=True but sending is not implemented yet — skipping {to_email}.")
    return False
