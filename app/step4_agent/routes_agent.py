"""
app/step4_agent/routes_agent.py — AI Job Agent API

Handles: GET /api/agent/status, GET /api/jobs/matches

Real, no external credentials needed to exercise these. The scan itself is
fully global — one shared 6-hour cycle for every registered user, no
per-user settings and no manual trigger endpoint (removed on purpose: the
countdown reaching zero is the only thing that starts a scan).
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends

from app.core.db import job_matches_collection, job_postings_collection, to_object_id
from app.core.security import get_current_user
from app.step4_agent import state as agent_state
from app.step4_agent.job_source_fetcher import SOURCES

router = APIRouter()


@router.get("/agent/status")
async def get_agent_status(user_id: str = Depends(get_current_user)):
    global_state = agent_state.get_global_agent_state()
    user_state = agent_state.ensure_agent_state(user_id)

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_count = job_matches_collection.count_documents({
        "user_id": user_id,
        "created_at": {"$gte": today_start},
    })

    return {
        # Global — identical for every user, driven by the shared scheduler.
        "next_scan_in_seconds": global_state["next_scan_in_seconds"],
        "last_scan_at": global_state["last_scan_at"],
        "last_fetch_fetched": global_state["last_fetch_fetched"],
        "last_fetch_saved": global_state["last_fetch_saved"],
        "sources": SOURCES,
        "jobs_in_pool": job_postings_collection.count_documents({}),
        # Personal — this user's own real counts.
        "new_matches_today": today_start_count,
        "emails_sent_today": user_state.get("emails_sent_today", 0),
        "total_matches": job_matches_collection.count_documents({"user_id": user_id}),
        "last_error": user_state.get("last_error"),
    }


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
            "source": job.get("source"),
            "description": job.get("description"),
            "skills_detected": job.get("skills_detected", []),
            "salary_min": job.get("salary_min"),
            "salary_max": job.get("salary_max"),
            "component_scores": match.get("component_scores", {}),
        })

    return {"count": len(results), "results": results}