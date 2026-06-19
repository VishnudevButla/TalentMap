"""
app/config.py — App Configuration via Pydantic BaseSettings

Loads all environment variables from the .env file into a typed settings object.
Use this instead of os.getenv() everywhere in the app — one source of truth.

How it works:
- Pydantic reads the .env file automatically
- Access settings anywhere: from app.config import settings
- settings.mongodb_uri, settings.aws_bucket_name, etc.
"""

# from pydantic_settings import BaseSettings

# class Settings(BaseSettings):
#     # MongoDB
#     mongodb_uri: str
#
#     # AWS S3
#     aws_access_key_id: str
#     aws_secret_access_key: str
#     aws_bucket_name: str
#     aws_region: str
#
#     # JWT (optional)
#     secret_key: str = "changeme"
#     algorithm: str = "HS256"
#     access_token_expire_minutes: int = 30
#
#     class Config:
#         env_file = ".env"

# settings = Settings()
