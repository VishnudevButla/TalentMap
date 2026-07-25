"""
app/routers/dashboard_api.py — Dashboard summary API

Handles: GET /api/dashboard/summary

Real, merges: latest resume analysis + top job matches + predicted
role/salary insights + AI Job Agent state + recent activity + today's
job-posting count. Client JS (static/js/dashboard.js) fetches this and
swaps it in over the server-rendered sample data, the same override
pattern already used for localStorage['latest_analysis'].
"""

from datetime import datetime

from fastapi import APIRouter, Depends

from app.core.db import analysis_collection, job_matches_collection, job_postings_collection, activity_log_collection, to_object_id
from app.core.security import get_current_user
from app.step4_agent import state as agent_state
from app.services.market_insights import get_current_match_summary

router = APIRouter()


@router.get("/dashboard/summary")
async def dashboard_summary(user_id: str = Depends(get_current_user)):
    latest = list(
        analysis_collection.find({"user_id": user_id}).sort("analyzed_at", -1).limit(1)
    )
    analysis = latest[0] if latest else None
    if analysis:
        analysis["_id"] = str(analysis["_id"])

    matches = list(
        job_matches_collection.find({"user_id": user_id}).sort("match_score", -1).limit(6)
    )
    job_matches = []
    for match in matches:
        job = job_postings_collection.find_one({"_id": to_object_id(match["job_id"])})
        if not job:
            continue
        job_matches.append({
            "title": job.get("title"), "company": job.get("company"),
            "location": job.get("location"), "remote_type": job.get("remote_type"),
            "match_score": match["match_score"], "status": match["status"],
            "url": job.get("url"),
        })

    agent_doc = agent_state.ensure_agent_state(user_id)
    next_scan_at = agent_doc.get("next_scan_at")
    next_scan_in_seconds = 0
    if next_scan_at:
        if isinstance(next_scan_at, str):
            next_scan_at = datetime.fromisoformat(next_scan_at)
        next_scan_in_seconds = max(0, int((next_scan_at - datetime.utcnow()).total_seconds()))

    activity = list(
        activity_log_collection.find({"user_id": user_id}).sort("created_at", -1).limit(5)
    )
    for a in activity:
        a["_id"] = str(a["_id"])

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    ai_jobs_found_today = job_postings_collection.count_documents({"fetched_at": {"$gte": today_start}})

    match = get_current_match_summary(user_id)

    return {
        "analysis": analysis,
        "match": match,  # {"score": ..., "status": ..., ...} or None — see market_insights.py
        "job_matches": job_matches,
        "agent": {
            "is_active": agent_doc.get("is_active", False),
            "next_scan_in_seconds": next_scan_in_seconds,
            "jobs_scanned_today": agent_doc.get("jobs_scanned_today", 0),
            "new_matches_today": agent_doc.get("new_matches_today", 0),
            "emails_sent_today": agent_doc.get("emails_sent_today", 0),
            "sources_monitored": len(agent_doc.get("sources_monitored", [])),
        },
        "activity": activity,
        "ai_jobs_found_today": ai_jobs_found_today,
    }
