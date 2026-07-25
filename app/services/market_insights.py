"""
app/services/market_insights.py — Dashboard match summary, derived from
real job matches.

Reads the user's top-ranked entry in job_matches_collection, joins to
job_postings_collection, and derives the dashboard's "Match score" tile
from it. Returns None when there's nothing to derive from yet (no job
matches) — callers should render an explicit empty state, not a
fabricated number.
"""

from typing import Any, Dict, Optional

from app.core.db import job_matches_collection, job_postings_collection, to_object_id


_STATUS_LABELS = {
    "excellent": "Excellent match",
    "good": "Strong match",
    "warn": "Needs improvement",
    "crit": "Needs improvement",
}


def _summarize_top_match(query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    top = list(job_matches_collection.find(query).sort("match_score", -1).limit(1))
    if not top:
        return None

    match = top[0]
    job = job_postings_collection.find_one({"_id": to_object_id(match["job_id"])})
    if not job:
        return None

    score = match["match_score"]
    status = match["status"]

    return {
        "score": score,
        "status": status,
        "status_label": _STATUS_LABELS.get(status, ""),
        "note": (
            f"Your best real match is <strong>{job.get('title', 'a role')}</strong> at "
            f"<strong>{job.get('company', 'a company')}</strong> — {score}% aligned, "
            f"based on live job postings."
        ),
    }


def get_current_match_summary(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Derives the dashboard's "Match score" tile from the user's single
    best-scoring real job match — there's no manual JD to score against
    anymore, so this is the closest real analogue: the best fit the AI Job
    Agent has actually found. Returns None until it's found at least one.
    """
    return _summarize_top_match({"user_id": user_id})


def get_match_summary_for_resume(resume_id: str) -> Optional[Dict[str, Any]]:
    """
    Same as get_current_match_summary, but scoped to one specific resume
    version rather than "the user's latest" — used by the Resume History
    page so each past analysis shows how it's actually doing against real
    job postings today, not a fabricated per-analysis score.
    """
    return _summarize_top_match({"resume_id": resume_id})
