"""
app/step4_agent/state.py — AI Job Agent state.

Real DB reads/writes, no external credentials involved. Two kinds of state:

- Global (agent_global_state_collection, single doc _id="global"): the
  shared scan schedule and last-cycle stats — same for every user, written
  once per cycle by scheduler.py's run_global_scan_cycle().
- Per-user (agent_state_collection, one doc per user_id): just the small
  amount of state that's genuinely personal — last scan timestamp, digest
  email count, last error. There is no per-user "active" flag or interval
  anymore — the scan is global and runs for every registered user.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict

from app.config import settings
from app.core.db import agent_state_collection, agent_global_state_collection

logger = logging.getLogger(__name__)

_GLOBAL_ID = "global"


# ---------------------------------------------------------------------------
# Global scan state — shared by every user
# ---------------------------------------------------------------------------

def get_global_agent_state() -> Dict[str, Any]:
    doc = agent_global_state_collection.find_one({"_id": _GLOBAL_ID}) or {}

    next_scan_at = doc.get("next_scan_at")
    next_scan_in_seconds = 0
    if next_scan_at:
        next_scan_in_seconds = max(0, int((next_scan_at - datetime.utcnow()).total_seconds()))

    return {
        "last_scan_at": doc.get("last_scan_at"),
        "next_scan_at": next_scan_at,
        "next_scan_in_seconds": next_scan_in_seconds,
        "last_fetch_fetched": doc.get("last_fetch_fetched", 0),
        "last_fetch_saved": doc.get("last_fetch_saved", 0),
        "last_users_matched": doc.get("last_users_matched", 0),
        "last_total_new_matches": doc.get("last_total_new_matches", 0),
    }


def record_global_scan(fetch_summary: Dict[str, int], users_matched: int, total_new_matches: int) -> None:
    now = datetime.utcnow()
    agent_global_state_collection.update_one(
        {"_id": _GLOBAL_ID},
        {"$set": {
            "last_scan_at": now,
            "next_scan_at": now + timedelta(minutes=settings.agent_scan_interval_minutes),
            "last_fetch_fetched": fetch_summary.get("fetched", 0),
            "last_fetch_saved": fetch_summary.get("saved", 0),
            "last_users_matched": users_matched,
            "last_total_new_matches": total_new_matches,
        }},
        upsert=True,
    )


# ---------------------------------------------------------------------------
# Per-user scan state — just the personal bits, no active flag or interval
# ---------------------------------------------------------------------------

def _default_state(user_id: str) -> Dict[str, Any]:
    return {
        "user_id": user_id,
        "last_scan_at": None,
        "emails_sent_today": 0,
        "counters_reset_date": datetime.utcnow().date().isoformat(),
        "last_scan_status": None,
        "last_error": None,
    }


def ensure_agent_state(user_id: str) -> Dict[str, Any]:
    doc = agent_state_collection.find_one({"user_id": user_id})
    if not doc:
        doc = _default_state(user_id)
        agent_state_collection.insert_one(doc)
    doc.pop("_id", None)
    return doc


def _reset_daily_counters_if_needed(doc: Dict[str, Any]) -> Dict[str, Any]:
    today = datetime.utcnow().date().isoformat()
    if doc.get("counters_reset_date") != today:
        doc["emails_sent_today"] = 0
        doc["counters_reset_date"] = today
    return doc


def advance_scan_clock(user_id: str, status: str = "ok", last_error: str = None) -> Dict[str, Any]:
    doc = ensure_agent_state(user_id)
    doc = _reset_daily_counters_if_needed(doc)

    updated = {
        "last_scan_at": datetime.utcnow(),
        "counters_reset_date": doc["counters_reset_date"],
        "last_scan_status": status,
        "last_error": last_error,
    }
    agent_state_collection.update_one({"user_id": user_id}, {"$set": updated}, upsert=True)
    logger.debug("Agent state updated: user_id=%s status=%s", user_id, status)
    return {**doc, **updated}