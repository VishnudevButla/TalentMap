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
        "notifications": {"email_alerts_enabled": False},
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
            "notifications": {"email_alerts_enabled": email_alerts_enabled},
            "updated_at": datetime.utcnow(),
        }},
        upsert=True,
    )
    return get_settings_context(user_id)
