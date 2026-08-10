"""
app/routers/dashboard_api.py — Dashboard summary API

Handles: GET /api/dashboard/summary

Real, merges: latest resume analysis + top job matches + demand-ranked
skills + AI Job Agent state (global schedule + this user's own counters) +
recent activity + today's job-posting count. Client JS
(static/js/dashboard.js) fetches this and hydrates the page — see
pages.py's dashboard_page() for why there's no server-side context.
"""

from datetime import datetime

from fastapi import APIRouter, Depends

from app.core.db import analysis_collection, job_matches_collection, job_postings_collection, activity_log_collection, to_object_id
from app.core.security import get_current_user
from app.step4_agent import state as agent_state
from app.step4_agent import scheduler as agent_scheduler
from app.step4_agent.job_source_fetcher import SOURCES
from app.services.market_insights import get_current_match_summary
from app.services.market_trends_data import get_demand_and_missing_skills

router = APIRouter()


@router.get("/dashboard/summary")
async def dashboard_summary(user_id: str = Depends(get_current_user)):
    latest = list(
        analysis_collection.find({"user_id": user_id}).sort("analyzed_at", -1).limit(1)
    )
    analysis = latest[0] if latest else None
    have_skills = set()
    if analysis:
        analysis["_id"] = str(analysis["_id"])
        have_skills = {s.lower() for s in analysis.get("matched_skills", [])}

    # One combined demand-skill ranking pass (a full job_postings scan)
    # instead of two independent ones — see get_demand_and_missing_skills()'s
    # docstring. The analysis doc always stores missing_skills=[] at analyze
    # time (see resume_analyze_2.py); the real, demand-ranked gap is
    # computed here instead of left fake-empty.
    demand_skills, missing_skills = get_demand_and_missing_skills(have_skills, demand_limit=6, missing_limit=6)
    if analysis:
        analysis["missing_skills"] = missing_skills

    matches = list(
        job_matches_collection.find({"user_id": user_id}).sort("match_score", -1).limit(6)
    )
    # One batched $in lookup instead of one find_one() per match (was up to
    # 6 extra round-trips per dashboard load) — projected to just the
    # fields this list actually renders, excluding the cached
    # component_embeddings matcher.py stores on every posting.
    job_ids = [to_object_id(m["job_id"]) for m in matches]
    jobs_by_id = {
        str(j["_id"]): j
        for j in job_postings_collection.find(
            {"_id": {"$in": job_ids}},
            {"title": 1, "company": 1, "company_logo_url": 1, "location": 1, "remote_type": 1, "url": 1, "skills_detected": 1, "salary_min": 1, "salary_max": 1},
        )
    }
    job_matches = []
    for match in matches:
        job = jobs_by_id.get(match["job_id"])
        if not job:
            continue
        job_matches.append({
            "job_id": match["job_id"],
            "title": job.get("title"), "company": job.get("company"),
            "company_logo_url": job.get("company_logo_url"),
            "location": job.get("location"), "remote_type": job.get("remote_type"),
            "match_score": match["match_score"], "status": match["status"],
            "url": job.get("url"), "skills_detected": job.get("skills_detected", []),
            "salary_min": job.get("salary_min"), "salary_max": job.get("salary_max"),
            "saved": match.get("saved", False),
        })

    # Scan schedule/stats are global now — one shared 6-hour cycle for every
    # user, no per-user active flag or interval.
    global_state = agent_state.get_global_agent_state()
    user_state = agent_state.ensure_agent_state(user_id)

    activity = list(
        activity_log_collection.find({"user_id": user_id}).sort("created_at", -1).limit(5)
    )
    for a in activity:
        a["_id"] = str(a["_id"])

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    ai_jobs_found_today = job_postings_collection.count_documents({"fetched_at": {"$gte": today_start}})

    # Real "new since last scan" — count of postings fetched after the
    # last global agent cycle. None (not 0) when the agent has never
    # scanned, so the frontend can tell "no scan yet" from "scanned, found
    # nothing new" instead of collapsing both into a fake "+0".
    last_scan_at = global_state["last_scan_at"]
    jobs_since_last_scan = None
    if last_scan_at:
        jobs_since_last_scan = job_postings_collection.count_documents({"fetched_at": {"$gt": last_scan_at}})

    new_matches_today = job_matches_collection.count_documents({
        "user_id": user_id, "created_at": {"$gte": today_start},
    })

    # Real skills coverage — matched vs. the matched+missing pool this same
    # request already computed above (get_demand_and_missing_skills), not a
    # separately-invented ratio.
    skills_coverage_pct = None
    total_skill_signal = len(have_skills) + len(missing_skills)
    if total_skill_signal:
        skills_coverage_pct = round(len(have_skills) / total_skill_signal * 100)

    month_start = today_start.replace(day=1)
    applied_this_month = job_matches_collection.count_documents({
        "user_id": user_id, "applied": True, "applied_at": {"$gte": month_start},
    })

    match = get_current_match_summary(user_id)

    return {
        "analysis": analysis,
        "match": match,  # {"score": ..., "status": ..., ...} or None — see market_insights.py
        "job_matches": job_matches,
        "demand_skills": demand_skills,  # real, ranked from job_postings_collection — see market_trends_data.py
        "agent": {
            "next_scan_in_seconds": global_state["next_scan_in_seconds"],
            "jobs_in_pool": job_postings_collection.count_documents({}),
            "new_matches_today": new_matches_today,
            "emails_sent_today": user_state.get("emails_sent_today", 0),
            "sources_monitored": len(SOURCES),
            "worker": agent_scheduler.get_worker_health(),
        },
        "activity": activity,
        "ai_jobs_found_today": ai_jobs_found_today,
        "jobs_since_last_scan": jobs_since_last_scan,
        "skills_coverage_pct": skills_coverage_pct,
        "applied_this_month": applied_this_month,
    }
