"""
app/config.py — App Configuration via Pydantic BaseSettings

Loads all environment variables from the .env file into a typed settings object.
Use this instead of os.getenv() everywhere in the app — one source of truth.

How it works:
- Pydantic reads the .env file automatically
- Access settings anywhere: from app.config import settings
- settings.mongodb_uri, settings.aws_bucket_name, etc.
"""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env relative to this file's location (app/ -> project root)
_ENV_FILE = Path(__file__).parent.parent / ".env"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",          # silently skip any extra keys in .env
    )

    # MongoDB — the full connection string, credentials included, lives
    # directly in .env. No separate username/password fields to splice in.
    mongodb_uri: str

    # AWS S3
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_bucket_name: Optional[str] = None
    aws_region: str = "us-east-1"

    # JWT configuration
    secret_key: str = "changeme"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # adzuna - used for searching for jobs
    JOB_API_PROVIDER: str = "adzuna"
    ADZUNA_APP_ID: Optional[str] = None
    ADZUNA_APP_KEY: Optional[str] = None
    ADZUNA_BASE_URL: str = "https://api.adzuna.com/v1/api"
    REMOTEOK_BASE_URL: str = "https://remoteok.com/api"

    # Email (SMTP or SES) — TODO(you): wire real sending, see
    # app/step4_agent/email_alerts.py. email_enabled is the master switch;
    # it stays False (silently skips sending) until you turn it on.
    email_enabled: bool = False
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from_address: Optional[str] = None
    ses_region: Optional[str] = None

    # Brevo API configuration
    brevo_api_key: Optional[str] = None
    brevo_sender_email: Optional[str] = None
    brevo_sender_name: str = "TalentMap Alerts"

    # Resend API configuration
    resend_api_key: Optional[str] = None
    resend_from_address: str = "onboarding@resend.dev"

    # AI Job Agent scheduler — set agent_scheduler_enabled=true in .env to
    # turn on the background scan + daily digest email jobs (see
    # app/step4_agent/scheduler.py's start_scheduler()).
    agent_scheduler_enabled: bool = False
    agent_scan_interval_minutes: int = 360  # 6 hours — global, shared by every user
    agent_max_sources_per_scan: int = 3

    # How long job postings/matches are kept before auto-expiring (MongoDB
    # TTL index, see app/core/db.py) — bounds collection growth from the
    # recurring scheduler.
    job_retention_days: int = 14

    # Hour (0-23, server/UTC time) the once-daily match digest email sends.
    email_digest_hour: int = 9

    # Public base URL of this app — used to build the "view all matches"
    # link in digest emails. Override in .env once deployed.
    app_base_url: str = "http://localhost:8000"

    # Google OAuth ("Continue with Google") — from a Google Cloud Console
    # OAuth 2.0 Client ID (Web application type). Both blank means the
    # feature is unconfigured; the login/callback routes return a clear
    # 503 instead of crashing until real credentials are set. The redirect
    # URI you register in Google Cloud must exactly match
    # f"{app_base_url}/api/auth/google/callback".
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None

    # Logging — see app/core/logger.py. One of DEBUG/INFO/WARNING/ERROR/CRITICAL.
    log_level: str = "INFO"

settings = Settings()
