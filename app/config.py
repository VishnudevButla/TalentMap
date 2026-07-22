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
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_bucket_name: str
    aws_region: str

    # JWT configuration
    secret_key: str = "changeme"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Job board API — TODO(you): integrate a real provider (Adzuna, JSearch,
    # Indeed Publisher, etc.) — see app/step4_agent/job_source_fetcher.py.
    # All optional/default-disabled so the app boots with zero .env changes.
    job_api_provider: Optional[str] = None
    job_api_key: Optional[str] = None
    job_api_base_url: Optional[str] = None

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

    # AI Job Agent scheduler — TODO(you): flip on once
    # app/step4_agent/scheduler.py's start_scheduler() is actually wired up.
    agent_scheduler_enabled: bool = False
    agent_scan_interval_minutes: int = 60
    agent_max_sources_per_scan: int = 3

    # Logging — see app/core/logger.py. One of DEBUG/INFO/WARNING/ERROR/CRITICAL.
    log_level: str = "INFO"

settings = Settings()
