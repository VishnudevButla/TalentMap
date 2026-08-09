"""
app/services/settings_data.py — Settings page data (real DB CRUD, no
external credentials involved).
"""

from datetime import datetime
from typing import Any, Dict

from app.core.db import user_settings_collection


def _default_settings(user_id: str) -> Dict[str, Any]:
    return {
        "user_id": user_id,
        "notifications": {
            "email_alerts_enabled": False,
            "digest_hour": 9,  # UTC hour (0-23) the daily digest is sent
        },
        "updated_at": datetime.utcnow(),
    }


def get_settings_context(user_id: str) -> Dict[str, Any]:
    doc = user_settings_collection.find_one({"user_id": user_id})
    if not doc:
        doc = _default_settings(user_id)
        user_settings_collection.insert_one(doc)
    doc.pop("_id", None)
    return doc


def update_notification_settings(user_id: str, email_alerts_enabled: bool) -> Dict[str, Any]:
    user_settings_collection.update_one(
        {"user_id": user_id},
        {"$set": {
            "notifications.email_alerts_enabled": email_alerts_enabled,
            "updated_at": datetime.utcnow(),
        }},
        upsert=True,
    )
    return get_settings_context(user_id)


def update_digest_hour(user_id: str, digest_hour: int) -> Dict[str, Any]:
    """
    Save the user's preferred UTC hour (0-23) for the daily job digest email.
    Celery Beat's hourly sweep reads this field to decide which users to email.
    """
    if not (0 <= digest_hour <= 23):
        raise ValueError(f"digest_hour must be 0-23, got {digest_hour}")
    user_settings_collection.update_one(
        {"user_id": user_id},
        {"$set": {
            "notifications.digest_hour": digest_hour,
            "updated_at": datetime.utcnow(),
        }},
        upsert=True,
    )
    return get_settings_context(user_id)

