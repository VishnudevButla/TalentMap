"""
app/services/market_trends_data.py — Market Trends page data.

Once app/step4_agent/job_source_fetcher.py is wired to a real job-board API
(see its TODO), job_postings_collection will fill up with real postings and
get_market_trends_context() below will compute genuine skill-demand
percentages from them — the aggregation logic itself is already real, it
just has nothing to aggregate yet. Until then this falls back to a small
labeled sample set (is_sample=True), same convention as
app/services/dashboard_data.py.
"""

from collections import Counter
from typing import Any, Dict, List, Set, Tuple

from app.core.db import job_postings_collection, analysis_collection


def _rank_demand_skills(have_skills: Set[str]) -> Tuple[List[Dict[str, Any]], int]:
    """
    Skill frequency across every stored posting, ranked highest-demand
    first, each flagged against `have_skills`. Shared by
    get_market_trends_context (scoped to a user's latest resume) and
    get_missing_skills_for_resume (scoped to one specific resume version).
    """
    postings = list(job_postings_collection.find({}))
    if not postings:
        return [], 0

    # A plain Python loop rather than a $unwind/$group pipeline, since
    # posting volume is expected to stay small enough that this is simpler
    # to read.
    skill_counts: Counter = Counter()
    for posting in postings:
        for skill in posting.get("skills_detected", []):
            skill_counts[skill.lower()] += 1

    total = len(postings)
    demand_skills = [
        {"name": skill, "score": round(count / total * 100), "have": skill in have_skills}
        for skill, count in skill_counts.most_common(12)
    ]
    return demand_skills, total


def get_missing_skills_for_resume(resume_id: str, limit: int = 6) -> List[Dict[str, str]]:
    """
    Real, demand-ranked skill gap for one specific resume version — used by
    the Resume History page so each past resume shows what it's actually
    missing against current market demand, not a fabricated JD diff.
    """
    analysis = analysis_collection.find_one({"resume_id": resume_id})
    have_skills = {s.lower() for s in analysis.get("matched_skills", [])} if analysis else set()

    demand_skills, total = _rank_demand_skills(have_skills)
    if total == 0:
        return []

    missing = [s for s in demand_skills if not s["have"]]
    return [
        {
            "name": s["name"],
            "demand": "high" if s["score"] >= 75 else "medium" if s["score"] >= 40 else "low",
        }
        for s in missing[:limit]
    ]


def _sample_market_trends_context() -> Dict[str, Any]:
    return {
        "is_sample": True,
        "demand_skills": [
            {"name": "python", "score": 96, "have": True},
            {"name": "sql", "score": 90, "have": True},
            {"name": "aws", "score": 88, "have": True},
            {"name": "kubernetes", "score": 81, "have": False},
            {"name": "docker", "score": 74, "have": True},
            {"name": "kafka", "score": 58, "have": False},
            {"name": "graphql", "score": 51, "have": False},
            {"name": "terraform", "score": 47, "have": False},
        ],
        "postings_analyzed": 0,
    }


def get_market_trends_context(user_id: str) -> Dict[str, Any]:
    latest_analyses = list(
        analysis_collection.find({"user_id": user_id}).sort("analyzed_at", -1).limit(1)
    )
    have_skills = set()
    if latest_analyses:
        have_skills = {s.lower() for s in latest_analyses[0].get("matched_skills", [])}

    demand_skills, total = _rank_demand_skills(have_skills)
    if total == 0:
        return _sample_market_trends_context()

    return {
        "is_sample": False,
        "demand_skills": demand_skills,
        "postings_analyzed": total,
    }
