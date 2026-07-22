"""
app/services/activity_log.py — write helper for activity_log_collection.

Any part of the app that wants an entry to show up on /activity or the
dashboard's Recent Activity feed calls log_activity(). Real, no external
credentials involved.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from app.core.db import activity_log_collection


def log_activity(user_id: str, type: str, message: str, icon: str = "info", meta: Optional[Dict[str, Any]] = None) -> None:
    activity_log_collection.insert_one({
        "user_id": user_id,
        "type": type,
        "message": message,
        "icon": icon,
        "created_at": datetime.utcnow(),
        "meta": meta or {},
    })
