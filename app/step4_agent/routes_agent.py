"""
app/step4_agent/routes_agent.py — AI Job Agent API

Handles: GET /api/agent/status, GET /api/jobs/matches

Real, no external credentials needed to exercise these. The scan itself is
fully global — one shared 6-hour cycle for every registered user, no
per-user settings and no manual trigger endpoint (removed on purpose: the
countdown reaching zero is the only thing that starts a scan).

_build_insights() composes the /agent page's "AI Insights" section from
data that already exists elsewhere (market_insights.py's best-match note,
market_trends_data.py's demand-ranked skill gap) — it doesn't compute
anything new, just turns real numbers already being served on other pages
into plain-language sentences about what the agent is doing for this
user, rather than scheduler internals.
"""

from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends

from app.core.db import analysis_collection, job_matches_collection, job_postings_collection, to_object_id
from app.core.security import get_current_user
from app.services.market_insights import get_current_match_summary
from app.services.market_trends_data import get_missing_skills_for_resume
from app.step4_agent import state as agent_state
from app.step4_agent import scheduler as agent_scheduler
from app.step4_agent.job_source_fetcher import SOURCES

router = APIRouter()

_SOURCE_LABELS = {"adzuna": "Adzuna", "remoteok": "RemoteOK"}


def _build_insights(user_id: str, jobs_in_pool: int, new_matches_today: int) -> List[Dict[str, str]]:
    sources_str = ", ".join(_SOURCE_LABELS.get(s, s) for s in SOURCES)
    insights = [{
        "icon": "radar",
        "text": f"Your agent is scanning {jobs_in_pool} live postings from {sources_str} for roles that fit your resume.",
    }]

    latest_analysis = list(
        analysis_collection.find({"user_id": user_id}).sort("analyzed_at", -1).limit(1)
    )
    if not latest_analysis:
        insights.append({
            "icon": "upload",
            "text": "Upload your resume to start getting AI-matched roles.",
        })
        return insights

    if new_matches_today:
        insights.append({
            "icon": "sparkles",
            "text": f"The agent found {new_matches_today} new match{'es' if new_matches_today != 1 else ''} for you today.",
        })

    best_match = get_current_match_summary(user_id)
    if best_match:
        insights.append({"icon": "target", "text": best_match["note"]})

    missing = get_missing_skills_for_resume(latest_analysis[0]["resume_id"], limit=1)
    if missing:
        insights.append({
            "icon": "trending-up",
            "text": f"Adding <strong>{missing[0]['name']}</strong> to your resume could open up more high-demand matches.",
        })

    return insights


@router.get("/agent/status")
async def get_agent_status(user_id: str = Depends(get_current_user)):
    global_state = agent_state.get_global_agent_state()
    user_state = agent_state.ensure_agent_state(user_id)

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_count = job_matches_collection.count_documents({
        "user_id": user_id,
        "created_at": {"$gte": today_start},
    })
    jobs_in_pool = job_postings_collection.count_documents({})

    return {
        # Global — identical for every user, driven by the shared scheduler.
        "next_scan_in_seconds": global_state["next_scan_in_seconds"],
        "last_scan_at": global_state["last_scan_at"],
        "last_fetch_fetched": global_state["last_fetch_fetched"],
        "last_fetch_saved": global_state["last_fetch_saved"],
        "sources": SOURCES,
        "jobs_in_pool": jobs_in_pool,
        # Real worker process health — reads the scheduler's leader-lock
        # renewal heartbeat, see scheduler.py's get_worker_health().
        "worker": agent_scheduler.get_worker_health(),
        # Personal — this user's own real counts.
        "new_matches_today": today_start_count,
        "emails_sent_today": user_state.get("emails_sent_today", 0),
        "total_matches": job_matches_collection.count_documents({"user_id": user_id}),
        "last_error": user_state.get("last_error"),
        # Plain-language summary of what the agent has actually done for
        # this user — see _build_insights() above.
        "insights": _build_insights(user_id, jobs_in_pool, today_start_count),
    }


@router.get("/jobs/matches")
async def get_job_matches(
    status: Optional[str] = None,
    remote_type: Optional[str] = None,
    sort: str = "score",  # "score" (default, /matches page) or "recent" (agent page's Recent Discoveries)
    limit: Optional[int] = None,
    user_id: str = Depends(get_current_user),
):
    filter_dict = {"user_id": user_id}
    if status and status != "all":
        filter_dict["status"] = status

    sort_field = "created_at" if sort == "recent" else "match_score"
    matches = list(job_matches_collection.find(filter_dict).sort(sort_field, -1))

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
            "discovered_at": match.get("created_at"),
            "source": job.get("source"),
            "description": job.get("description"),
            "skills_detected": job.get("skills_detected", []),
            "salary_min": job.get("salary_min"),
            "salary_max": job.get("salary_max"),
            "component_scores": match.get("component_scores", {}),
        })
        if limit and len(results) >= limit:
            break

    return {"count": len(results), "results": results}