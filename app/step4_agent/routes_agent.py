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

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.db import analysis_collection, job_matches_collection, job_postings_collection, to_object_id
from app.core.security import get_current_user
from app.services.activity_log import log_activity
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


def _sources_breakdown() -> List[Dict[str, object]]:
    """
    Real per-source counts in one aggregation query (not one
    count_documents() per source) — backs the Sources card's actual
    breakdown instead of just a bare "N sources" count.
    """
    counts = {row["_id"]: row["count"] for row in job_postings_collection.aggregate([
        {"$group": {"_id": "$source", "count": {"$sum": 1}}}
    ])}
    return [
        {"source": s, "label": _SOURCE_LABELS.get(s, s), "count": counts.get(s, 0)}
        for s in SOURCES
    ]


def _match_distribution(user_id: str) -> Dict[str, int]:
    """
    This user's real matches grouped by status — always all four keys
    present (0 where there are none), so the frontend never has to guess
    whether a missing key means "zero" or "not computed yet."
    """
    counts = {row["_id"]: row["count"] for row in job_matches_collection.aggregate([
        {"$match": {"user_id": user_id}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ])}
    return {status: counts.get(status, 0) for status in ("excellent", "good", "warn", "crit")}


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
    match_distribution = _match_distribution(user_id)

    return {
        # Global — identical for every user, driven by the shared scheduler.
        "next_scan_in_seconds": global_state["next_scan_in_seconds"],
        "last_scan_at": global_state["last_scan_at"],
        "last_fetch_fetched": global_state["last_fetch_fetched"],
        "last_fetch_saved": global_state["last_fetch_saved"],
        "sources": SOURCES,
        "sources_breakdown": _sources_breakdown(),
        "jobs_in_pool": jobs_in_pool,
        # Real, previously computed every cycle (record_global_scan) but
        # never surfaced anywhere in the UI until now.
        "last_users_matched": global_state["last_users_matched"],
        "last_total_new_matches": global_state["last_total_new_matches"],
        # Real worker process health — reads the scheduler's leader-lock
        # renewal heartbeat, see scheduler.py's get_worker_health().
        "worker": agent_scheduler.get_worker_health(),
        # Personal — this user's own real counts.
        "new_matches_today": today_start_count,
        "emails_sent_today": user_state.get("emails_sent_today", 0),
        "total_matches": job_matches_collection.count_documents({"user_id": user_id}),
        "match_distribution": match_distribution,
        "high_quality_matches": match_distribution["excellent"] + match_distribution["good"],
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

    # One batched $in lookup instead of one find_one() per match — this
    # endpoint could previously fire dozens of individual round-trips for
    # a user with many matches. Excludes component_embeddings/job_entities
    # (matcher.py's internal scoring data, ~40KB/doc) since nothing below
    # reads them.
    job_ids = [to_object_id(m["job_id"]) for m in matches]
    jobs_by_id = {
        str(j["_id"]): j
        for j in job_postings_collection.find(
            {"_id": {"$in": job_ids}},
            {"component_embeddings": 0, "job_entities": 0},
        )
    }

    results = []
    for match in matches:
        job = jobs_by_id.get(match["job_id"])
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


@router.get("/jobs/matches/{job_id}")
async def get_job_match_detail(job_id: str, user_id: str = Depends(get_current_user)):
    """
    Everything the job-details page needs for one match, computed fresh
    rather than trusting client-cached list data: real matched/missing
    skills for THIS specific posting (resume's full extracted skill list,
    not the display-capped matched_skills field, against this job's own
    skills_detected), and "similar jobs" from this same user's other real
    matches rather than a separate, fabricated similarity metric.
    """
    match = job_matches_collection.find_one({"user_id": user_id, "job_id": job_id})
    if not match:
        raise HTTPException(status_code=404, detail="Match not found.")

    top_match = job_matches_collection.find_one({"user_id": user_id}, sort=[("match_score", -1)])
    is_best_match = bool(top_match) and top_match["job_id"] == job_id

    job = job_postings_collection.find_one(
        {"_id": to_object_id(job_id)},
        {"component_embeddings": 0, "job_entities": 0},
    )
    if not job:
        raise HTTPException(status_code=404, detail="This job posting is no longer available.")

    first_viewed_at = match.get("first_viewed_at")
    if not first_viewed_at:
        first_viewed_at = datetime.utcnow()
        job_matches_collection.update_one(
            {"_id": match["_id"]}, {"$set": {"first_viewed_at": first_viewed_at}}
        )

    resume_skills = set()
    analysis = analysis_collection.find_one({"resume_id": match.get("resume_id")})
    if analysis:
        resume_skills = {s.lower() for s in analysis.get("entities", {}).get("skills", [])}
    job_skills = job.get("skills_detected", [])
    matched_skills = [s for s in job_skills if s.lower() in resume_skills]
    missing_skills = [s for s in job_skills if s.lower() not in resume_skills]

    other_matches = list(
        job_matches_collection.find({"user_id": user_id, "job_id": {"$ne": job_id}})
        .sort("match_score", -1)
        .limit(3)
    )
    other_jobs_by_id = {
        str(j["_id"]): j
        for j in job_postings_collection.find(
            {"_id": {"$in": [to_object_id(m["job_id"]) for m in other_matches]}},
            {"title": 1, "company": 1, "company_logo_url": 1, "location": 1, "remote_type": 1, "salary_min": 1, "salary_max": 1},
        )
    }
    similar_jobs = []
    for m in other_matches:
        oj = other_jobs_by_id.get(m["job_id"])
        if not oj:
            continue
        similar_jobs.append({
            "job_id": m["job_id"], "title": oj.get("title"), "company": oj.get("company"),
            "company_logo_url": oj.get("company_logo_url"), "location": oj.get("location"),
            "remote_type": oj.get("remote_type"), "match_score": m["match_score"],
            "salary_min": oj.get("salary_min"), "salary_max": oj.get("salary_max"),
        })

    return {
        "job_id": job_id,
        "title": job.get("title"), "company": job.get("company"),
        "company_logo_url": job.get("company_logo_url"),
        "location": job.get("location"), "remote_type": job.get("remote_type"),
        "url": job.get("url"), "source": job.get("source"),
        "description": job.get("description"),
        "posted_at": job.get("posted_at"),
        "salary_min": job.get("salary_min"), "salary_max": job.get("salary_max"),
        "match_score": match["match_score"], "status": match["status"],
        "is_best_match": is_best_match,
        "component_scores": match.get("component_scores", {}),
        "matched_skills": matched_skills, "missing_skills": missing_skills,
        "applied": match.get("applied", False), "applied_at": match.get("applied_at"),
        "saved": match.get("saved", False), "saved_at": match.get("saved_at"),
        "first_viewed_at": first_viewed_at,
        "discovered_at": match.get("created_at"),
        "similar_jobs": similar_jobs,
    }


class ApplyIn(BaseModel):
    applied: bool


@router.patch("/jobs/matches/{job_id}/apply")
async def set_job_applied(job_id: str, body: ApplyIn, user_id: str = Depends(get_current_user)):
    update = {"applied": body.applied, "applied_at": datetime.utcnow() if body.applied else None}
    result = job_matches_collection.find_one_and_update(
        {"user_id": user_id, "job_id": job_id}, {"$set": update}
    )
    if not result:
        raise HTTPException(status_code=404, detail="Match not found.")

    if body.applied:
        job = job_postings_collection.find_one({"_id": to_object_id(job_id)}, {"title": 1, "company": 1})
        if job:
            log_activity(
                user_id, "job_applied",
                f"Applied to {job.get('title', 'a role')} at {job.get('company', 'a company')}",
                icon="briefcase", meta={"job_id": job_id},
            )

    return update


class SaveIn(BaseModel):
    saved: bool


@router.patch("/jobs/matches/{job_id}/save")
async def set_job_saved(job_id: str, body: SaveIn, user_id: str = Depends(get_current_user)):
    update = {"saved": body.saved, "saved_at": datetime.utcnow() if body.saved else None}
    result = job_matches_collection.update_one(
        {"user_id": user_id, "job_id": job_id}, {"$set": update}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Match not found.")
    return update