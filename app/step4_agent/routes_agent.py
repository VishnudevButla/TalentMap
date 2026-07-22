"""
app/step4_agent/routes_agent.py — AI Job Agent API

Handles: GET /api/agent/status, POST /api/agent/settings,
POST /api/agent/scan-now, GET /api/jobs/matches

All real — no external credentials needed to exercise these. scan-now
manually triggers the same run_scan_cycle() a real scheduler (TODO in
scheduler.py) would call automatically.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.db import job_matches_collection, job_postings_collection, to_object_id
from app.core.security import get_current_user
from app.step4_agent import state as agent_state
from app.step4_agent.scheduler import run_scan_cycle

router = APIRouter()


@router.get("/agent/status")
async def get_agent_status(user_id: str = Depends(get_current_user)):
    doc = agent_state.ensure_agent_state(user_id)
    next_scan_at = doc.get("next_scan_at")
    next_scan_in_seconds = 0
    if next_scan_at:
        if isinstance(next_scan_at, str):
            next_scan_at = datetime.fromisoformat(next_scan_at)
        next_scan_in_seconds = max(0, int((next_scan_at - datetime.utcnow()).total_seconds()))

    return {
        "is_active": doc.get("is_active", False),
        "status": doc.get("status", "paused"),
        "sources_monitored": doc.get("sources_monitored", []),
        "jobs_scanned_today": doc.get("jobs_scanned_today", 0),
        "new_matches_today": doc.get("new_matches_today", 0),
        "emails_sent_today": doc.get("emails_sent_today", 0),
        "next_scan_in_seconds": next_scan_in_seconds,
        "last_error": doc.get("last_error"),
    }


class AgentSettingsUpdate(BaseModel):
    is_active: Optional[bool] = None
    scan_interval_minutes: Optional[int] = None


@router.post("/agent/settings")
async def update_agent_settings(
    body: AgentSettingsUpdate, user_id: str = Depends(get_current_user)
):
    return agent_state.update_agent_settings(
        user_id, is_active=body.is_active, scan_interval_minutes=body.scan_interval_minutes
    )


@router.post("/agent/scan-now")
async def scan_now(user_id: str = Depends(get_current_user)):
    return await run_scan_cycle(user_id)


@router.get("/jobs/matches")
async def get_job_matches(
    status: Optional[str] = None,
    remote_type: Optional[str] = None,
    user_id: str = Depends(get_current_user),
):
    filter_dict = {"user_id": user_id}
    if status and status != "all":
        filter_dict["status"] = status

    matches = list(job_matches_collection.find(filter_dict).sort("match_score", -1))

    results = []
    for match in matches:
        job = job_postings_collection.find_one({"_id": to_object_id(match["job_id"])})
        if not job:
            continue
        if remote_type and remote_type != "all" and job.get("remote_type") != remote_type:
            continue
        results.append({
            "job_id": match["job_id"],
            "title": job.get("title"),
            "company": job.get("company"),
            "company_logo_url": job.get("company_logo_url"),
            "location": job.get("location"),
            "remote_type": job.get("remote_type"),
            "url": job.get("url"),
            "match_score": match["match_score"],
            "status": match["status"],
            "applied": match.get("applied", False),
            "posted_at": job.get("posted_at"),
        })

    return {"count": len(results), "results": results}
