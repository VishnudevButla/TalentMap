"""
app/step4_agent/state.py — AI Job Agent per-user state.

Real DB reads/writes against agent_state_collection, no external
credentials involved.
"""

from datetime import datetime, timedelta
from typing import Any, Dict

from app.core.db import agent_state_collection

DEFAULT_SOURCES = ["default"]  # TODO(you): populate with real source names
                                # once job_source_fetcher.py supports more
                                # than one provider.


def _default_state(user_id: str, scan_interval_minutes: int) -> Dict[str, Any]:
    now = datetime.utcnow()
    return {
        "user_id": user_id,
        "is_active": False,
        "scan_interval_minutes": scan_interval_minutes,
        "sources_monitored": DEFAULT_SOURCES,
        "last_scan_at": None,
        "next_scan_at": now + timedelta(minutes=scan_interval_minutes),
        "jobs_scanned_today": 0,
        "new_matches_today": 0,
        "emails_sent_today": 0,
        "counters_reset_date": now.date().isoformat(),
        "status": "paused",
        "last_error": None,
    }


def ensure_agent_state(user_id: str, scan_interval_minutes: int = 60) -> Dict[str, Any]:
    doc = agent_state_collection.find_one({"user_id": user_id})
    if not doc:
        doc = _default_state(user_id, scan_interval_minutes)
        agent_state_collection.insert_one(doc)
    doc.pop("_id", None)
    return doc


def _reset_daily_counters_if_needed(doc: Dict[str, Any]) -> Dict[str, Any]:
    today = datetime.utcnow().date().isoformat()
    if doc.get("counters_reset_date") != today:
        doc["jobs_scanned_today"] = 0
        doc["new_matches_today"] = 0
        doc["emails_sent_today"] = 0
        doc["counters_reset_date"] = today
    return doc


def advance_scan_clock(
    user_id: str, jobs_scanned: int, new_matches: int, emails_sent: int, status: str = "active", last_error: str = None
) -> Dict[str, Any]:
    doc = ensure_agent_state(user_id)
    doc = _reset_daily_counters_if_needed(doc)

    now = datetime.utcnow()
    interval = doc.get("scan_interval_minutes", 60)

    updated = {
        "last_scan_at": now,
        "next_scan_at": now + timedelta(minutes=interval),
        "jobs_scanned_today": doc.get("jobs_scanned_today", 0) + jobs_scanned,
        "new_matches_today": doc.get("new_matches_today", 0) + new_matches,
        "emails_sent_today": doc.get("emails_sent_today", 0) + emails_sent,
        "counters_reset_date": doc["counters_reset_date"],
        "status": status,
        "last_error": last_error,
    }
    agent_state_collection.update_one({"user_id": user_id}, {"$set": updated}, upsert=True)
    return {**doc, **updated}


def update_agent_settings(user_id: str, is_active: bool = None, scan_interval_minutes: int = None) -> Dict[str, Any]:
    doc = ensure_agent_state(user_id)
    updates: Dict[str, Any] = {}
    if is_active is not None:
        updates["is_active"] = is_active
        updates["status"] = "active" if is_active else "paused"
    if scan_interval_minutes is not None:
        updates["scan_interval_minutes"] = scan_interval_minutes
        updates["next_scan_at"] = datetime.utcnow() + timedelta(minutes=scan_interval_minutes)
    if updates:
        agent_state_collection.update_one({"user_id": user_id}, {"$set": updates}, upsert=True)
    return {**doc, **updates}
