"""
app/services/settings_data.py — Settings page data (real DB CRUD, no
external credentials involved).

notifications.email_frequency and match_threshold are both actually read
by the live worker (app/step4_agent/scheduler.py's send_daily_digest and
run_scan_cycle, app/step4_agent/matcher.py's activity-log gate) — not
just stored and displayed. See those files for exactly how.
"""

from datetime import datetime
from typing import Any, Dict

from app.core.db import user_settings_collection

EMAIL_FREQUENCIES = ("immediate", "daily", "weekly", "never")
DEFAULT_MATCH_THRESHOLD = 70  # matches the score cutoff this app used before it was configurable


def _default_settings(user_id: str) -> Dict[str, Any]:
    return {
        "user_id": user_id,
        "notifications": {
            "email_alerts_enabled": False,
            "digest_hour": 9,  # UTC hour (0-23) the daily digest is sent
            "email_frequency": "daily",  # "immediate" | "daily" | "weekly" | "never"
        },
        "match_threshold": DEFAULT_MATCH_THRESHOLD,  # score >= this is "worth telling you about"
        "updated_at": datetime.utcnow(),
    }


def get_settings_context(user_id: str) -> Dict[str, Any]:
    doc = user_settings_collection.find_one({"user_id": user_id})
    if not doc:
        doc = _default_settings(user_id)
        user_settings_collection.insert_one(doc)
    doc.pop("_id", None)
    # Docs created before a field existed just won't have it — default
    # rather than guess, same pattern used across this app's other
    # backward-compatible reads (e.g. resume_collection.is_active).
    doc.setdefault("match_threshold", DEFAULT_MATCH_THRESHOLD)
    doc["notifications"].setdefault("email_frequency", "daily")
    return doc


def get_user_notification_prefs(user_id: str) -> Dict[str, Any]:
    """
    Thin accessor for the worker (scheduler.py, matcher.py) — avoids every
    call site needing to know the full settings document shape.
    """
    doc = get_settings_context(user_id)
    return {
        "email_alerts_enabled": doc["notifications"]["email_alerts_enabled"],
        "email_frequency": doc["notifications"]["email_frequency"],
        "match_threshold": doc["match_threshold"],
    }


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
    """Save the user's preferred UTC hour (0-23) — used only for "daily" frequency; see scheduler.py."""
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


def update_email_frequency(user_id: str, email_frequency: str) -> Dict[str, Any]:
    if email_frequency not in EMAIL_FREQUENCIES:
        raise ValueError(f"email_frequency must be one of {EMAIL_FREQUENCIES}, got {email_frequency!r}")
    user_settings_collection.update_one(
        {"user_id": user_id},
        {"$set": {
            "notifications.email_frequency": email_frequency,
            "updated_at": datetime.utcnow(),
        }},
        upsert=True,
    )
    return get_settings_context(user_id)


def update_match_threshold(user_id: str, match_threshold: int) -> Dict[str, Any]:
    if not (0 <= match_threshold <= 100):
        raise ValueError(f"match_threshold must be 0-100, got {match_threshold}")
    user_settings_collection.update_one(
        {"user_id": user_id},
        {"$set": {
            "match_threshold": match_threshold,
            "updated_at": datetime.utcnow(),
        }},
        upsert=True,
    )
    return get_settings_context(user_id)
