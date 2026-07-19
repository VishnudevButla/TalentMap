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
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env relative to this file's location (app/ -> project root)
_ENV_FILE = Path(__file__).parent.parent / ".env"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",          # silently skip any extra keys in .env
    )

    # MongoDB
    mongodb_uri: str
    mongodb_username: str = ""
    mongodb_password: str = ""

    # AWS S3
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_bucket_name: str
    aws_region: str

    # JWT configuration
    secret_key: str = "changeme"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

settings = Settings()
