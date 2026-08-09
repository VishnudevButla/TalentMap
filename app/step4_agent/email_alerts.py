"""
app/step4_agent/email_alerts.py — Job Match Email Alerts

Sends transactional match emails to users using:
  1. Resend API (if settings.resend_api_key is configured)
  2. Brevo API (if settings.brevo_api_key is configured)
  3. Standard SMTP relay (using settings.smtp_host/port/username/password)
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List

import resend
from bson import ObjectId

from app.config import settings
from app.core.db import job_postings_collection

logger = logging.getLogger(__name__)


MAX_DIGEST_MATCHES = 10


def send_match_alert_email(to_email: str, matches: List[Dict[str, Any]]) -> bool:
    """
    Sends the once-daily match digest email: the top MAX_DIGEST_MATCHES
    matches (caller is expected to pass matches already sorted by score,
    highest first), plus a CTA button linking back to the dashboard for
    the full list.

    Args:
        to_email: Target candidate email address.
        matches: List of match dictionaries from matcher.py, best-first.

    Returns:
        bool: True if sent successfully, False otherwise.
    """
    if not settings.email_enabled:
        logger.debug("Email sending disabled — skipping alert (%d matches)", len(matches))
        return False

    if not matches:
        logger.debug("No matches to send — skipping alert")
        return False

    matches = matches[:MAX_DIGEST_MATCHES]

    # Never log `to_email` for privacy
    logger.info("Preparing email digest containing %d matches", len(matches))

    # Fetch job details from the database
    job_ids = []
    for m in matches:
        jid = m.get("job_id")
        if jid:
            try:
                job_ids.append(ObjectId(jid))
            except Exception:
                pass
                
    job_docs = {
        str(j["_id"]): j for j in job_postings_collection.find({"_id": {"$in": job_ids}})
    }

    # Construct match listings for the email body
    items_html = []
    for m in matches:
        job = job_docs.get(m.get("job_id", ""))
        if not job:
            continue
        
        title = job.get("title", "Job Posting")
        company = job.get("company", "Unknown Company")
        location = job.get("location", "Remote/Onsite")
        url = job.get("url", "#")
        score = m.get("match_score", 0)

        # Color-coded pill based on score
        if score >= 85:
            pill_color = "#2e7d32"  # Green
            text_color = "#ffffff"
        elif score >= 70:
            pill_color = "#1565c0"  # Blue
            text_color = "#ffffff"
        elif score >= 45:
            pill_color = "#ef6c00"  # Orange
            text_color = "#ffffff"
        else:
            pill_color = "#c62828"  # Red
            text_color = "#ffff ff"

        salary_text = ""
        s_min = job.get("salary_min")
        s_max = job.get("salary_max")
        if s_min and s_max:
            salary_text = f" | Salary: ${s_min:,.0f} - ${s_max:,.0f}"
        elif s_min:
            salary_text = f" | Salary: Min ${s_min:,.0f}"

        items_html.append(f"""
        <div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px; margin-bottom: 16px; background-color: #ffffff; text-align: left;">
            <div style="margin-bottom: 8px;">
                <table width="100%" border="0" cellspacing="0" cellpadding="0">
                    <tr>
                        <td align="left">
                            <h3 style="margin: 0; font-size: 18px; color: #1a73e8;">{title}</h3>
                        </td>
                        <td align="right" width="100">
                            <span style="background-color: {pill_color}; color: {text_color}; padding: 4px 8px; border-radius: 12px; font-size: 12px; font-weight: bold; text-transform: uppercase;">
                                {score}% Match
                            </span>
                        </td>
                    </tr>
                </table>
            </div>
            <p style="margin: 0 0 8px 0; font-size: 14px; font-weight: bold; color: #5f6368;">{company}</p>
            <p style="margin: 0 0 12px 0; font-size: 13px; color: #70757a;">
                Location: {location}{salary_text}
            </p>
            <a href="{url}" target="_blank" style="display: inline-block; background-color: #1a73e8; color: #ffffff; padding: 8px 16px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;">
                View & Apply
            </a>
        </div>
        """)

    if not items_html:
        logger.warning("No valid job details found for the match list — skipping email")
        return False

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Your Daily Job Matches</title>
    </head>
    <body style="font-family: Arial, sans-serif; background-color: #f1f3f4; margin: 0; padding: 20px; color: #3c4043;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
            <div style="background: linear-gradient(135deg, #1a73e8, #1557b0); padding: 24px; text-align: center; color: #ffffff;">
                <h1 style="margin: 0; font-size: 24px; font-weight: bold;">TalentMap Alerts</h1>
                <p style="margin: 8px 0 0 0; font-size: 16px; opacity: 0.9;">Your Daily Best-Fit Job Matches</p>
            </div>
            <div style="padding: 24px;">
                <p style="margin: 0 0 20px 0; font-size: 16px; line-height: 1.5; text-align: left;">
                    Hello, <br><br>
                    We found <strong>{len(items_html)}</strong> new job matches that align with your resume and skills. Here are the best fits for you today:
                </p>
                
                {"".join(items_html)}

                <div style="text-align: center; margin: 24px 0 8px 0;">
                    <a href="{settings.app_base_url}/dashboard" target="_blank" style="display: inline-block; background-color: #1557b0; color: #ffffff; padding: 12px 28px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;">
                        View your top 10 matches &rarr;
                    </a>
                </div>

                <p style="margin: 24px 0 0 0; font-size: 12px; color: #70757a; text-align: center; line-height: 1.5;">
                    You are receiving this email because you registered for automated matches on TalentMap.<br>
                    To configure your settings or disable these alerts, log in to your dashboard.
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    # --- Option 1: Send via Resend API ---
    if settings.resend_api_key:
        logger.info("Sending email via Resend API...")
        resend.api_key = settings.resend_api_key
        from_address = settings.resend_from_address or "onboarding@resend.dev"
        
        params = {
            "from": from_address,
            "to": [to_email],
            "subject": "Your Daily TalentMap Job Matches",
            "html": html_content,
        }
        
        try:
            r = resend.Emails.send(params)
            logger.info("Resend email sent successfully: %s", r)
            return True
        except Exception as exc:
            logger.error("Failed to send email via Resend API: %s", exc)
            if not (getattr(settings, "brevo_api_key", None) or settings.smtp_host):
                return False

    # --- Option 2: Send via Brevo API ---
    brevo_key = getattr(settings, "brevo_api_key", None)
    if brevo_key:
        logger.info("Sending email via Brevo API...")
        try:
            import sib_api_v3_sdk
            from sib_api_v3_sdk.rest import ApiException

            configuration = sib_api_v3_sdk.Configuration()
            configuration.api_key["api-key"] = settings.brevo_api_key

            api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
                sib_api_v3_sdk.ApiClient(configuration)
            )

            sender_email = settings.brevo_sender_email or "alerts@talentmap.com"
            sender_name = settings.brevo_sender_name or "TalentMap Alerts"

            send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
                sender={"name": sender_name, "email": sender_email},
                to=[{"email": to_email}],
                subject="Your Daily TalentMap Job Matches",
                html_content=html_content,
            )

            api_instance.send_transac_email(send_smtp_email)
            logger.info("Brevo email sent successfully")
            return True
        except Exception as exc:
            logger.error("Failed to send email via Brevo API: %s", exc)
            if not settings.smtp_host:
                return False

    # --- Option 3: Send via standard SMTP ---
    if settings.smtp_host:
        logger.info("Sending email via SMTP relay (%s)...", settings.smtp_host)
        
        from_address = settings.smtp_from_address or "alerts@talentmap.com"
        
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Your Daily TalentMap Job Matches"
        msg["From"] = from_address
        msg["To"] = to_email
        
        msg.attach(MIMEText(html_content, "html"))
        
        try:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
            server.starttls()
            if settings.smtp_username and settings.smtp_password:
                server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(from_address, [to_email], msg.as_string())
            server.quit()
            logger.info("SMTP email sent successfully")
            return True
        except Exception as exc:
            logger.error("Failed to send email via SMTP: %s", exc)
            return False

    logger.warning("No valid email provider (Resend, Brevo, SMTP) configured. Email sending failed.")
    return False
