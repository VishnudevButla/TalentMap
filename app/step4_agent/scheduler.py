"""
app/step4_agent/scheduler.py — AI Job Agent scan cycle + scheduler.

run_scan_cycle() is a real, working orchestrator today: fetch → upsert
postings → match → advance state → conditionally email → log activity.
It runs end-to-end with zero job postings (since job_source_fetcher.py's
TODO isn't filled in yet) — that proves the plumbing works before any
external integration exists.

start_scheduler() is the TODO(you) piece: nothing currently calls
run_scan_cycle() automatically on a timer.
"""

from datetime import datetime
from typing import Any, Dict

from bson import ObjectId

from app.core.db import job_postings_collection, user_collection
from app.config import settings
from app.step4_agent import state as agent_state
from app.step4_agent.job_source_fetcher import fetch_jobs_from_source
from app.step4_agent.matcher import run_matching_for_user
from app.step4_agent.email_alerts import send_match_alert_email
from app.services.activity_log import log_activity


def _upsert_postings(raw_postings) -> int:
    count = 0
    for posting in raw_postings:
        job_postings_collection.update_one(
            {"source": posting.get("source"), "external_id": posting.get("external_id")},
            {"$set": {**posting, "fetched_at": datetime.utcnow()}},
            upsert=True,
        )
        count += 1
    return count


async def run_scan_cycle(user_id: str) -> Dict[str, Any]:
    doc = agent_state.ensure_agent_state(user_id, settings.agent_scan_interval_minutes)
    sources = doc.get("sources_monitored", ["default"])[: settings.agent_max_sources_per_scan]

    jobs_scanned = 0
    try:
        for source in sources:
            raw_postings = fetch_jobs_from_source(source, keywords=[])
            jobs_scanned += _upsert_postings(raw_postings)

        new_matches = run_matching_for_user(user_id)

        emails_sent = 0
        try:
            user_doc = user_collection.find_one({"_id": ObjectId(user_id)}) or {}
        except Exception:
            user_doc = {}
        to_email = user_doc.get("email")
        if new_matches and to_email and settings.email_enabled:
            if send_match_alert_email(to_email, new_matches):
                emails_sent = 1

        updated_state = agent_state.advance_scan_clock(
            user_id, jobs_scanned=jobs_scanned, new_matches=len(new_matches), emails_sent=emails_sent
        )

        log_activity(
            user_id=user_id,
            type="agent_scan",
            message=f"Agent scan complete — {jobs_scanned} jobs scanned, {len(new_matches)} new matches",
            icon="briefcase",
        )
        return updated_state

    except Exception as exc:  # keep the agent resilient — one bad scan shouldn't wedge the state
        return agent_state.advance_scan_clock(
            user_id, jobs_scanned=jobs_scanned, new_matches=0, emails_sent=0,
            status="error", last_error=str(exc),
        )


def start_scheduler(app) -> None:
    """
    TODO(you): nothing calls run_scan_cycle() on a timer yet. Once you're
    ready for the AI Job Agent to actually run periodically:

    1. `pip install apscheduler` (already listed in requirements.txt).
    2. In app/main.py, switch to FastAPI's lifespan context manager and
       call this function on startup:

         from contextlib import asynccontextmanager
         from app.step4_agent.scheduler import start_scheduler

         @asynccontextmanager
         async def lifespan(app: FastAPI):
             start_scheduler(app)
             yield

         app = FastAPI(title="TalentMap API", version="1.0.0", lifespan=lifespan)

    3. Implement start_scheduler() itself, e.g.:

         from apscheduler.schedulers.asyncio import AsyncIOScheduler
         from app.core.db import agent_state_collection

         def start_scheduler(app):
             if not settings.agent_scheduler_enabled:
                 return
             scheduler = AsyncIOScheduler()

             async def scan_all_active_users():
                 for doc in agent_state_collection.find({"is_active": True}):
                     await run_scan_cycle(doc["user_id"])

             scheduler.add_job(scan_all_active_users, "interval",
                                minutes=settings.agent_scan_interval_minutes)
             scheduler.start()

    Until this is implemented, /api/agent/scan-now (routes_agent.py) is the
    only way run_scan_cycle() gets called — which is enough to verify the
    whole pipeline works.
    """
    if not settings.agent_scheduler_enabled:
        print("[scheduler] agent_scheduler_enabled=False — AI Job Agent will not run automatically. "
              "Use POST /api/agent/scan-now, or see start_scheduler()'s docstring to wire a real scheduler.")
        return
    raise NotImplementedError("start_scheduler() TODO(you): see docstring above.")
