"""
app/services/market_trends_data.py — Market Trends page data.

Everything here is derived from real data in job_postings_collection /
job_matches_collection / analysis_collection — no fabricated numbers, no
placeholder ML, and no whole-page "sample" fallback. When there isn't
enough real data yet to compute a section honestly (e.g. no postings at
all, or too short a time span to detect a trend), that section returns
None/[]/0 rather than a guessed value, and the frontend
(static/js/market-trends.js) renders an honest "not enough data yet"
state for just that section.
"""

from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.db import job_postings_collection, analysis_collection, job_matches_collection, to_object_id

# Minimum span of real posting timestamps (in days) before a recent-vs-prior
# trend comparison is considered meaningful rather than noise.
_MIN_TREND_SPAN_DAYS = 4
_MAX_WINDOW_DAYS = 15


# ---------------------------------------------------------------------------
# Skill demand (shared by the demand bars, opportunity skills, and the
# per-resume skill gap used by the Resume History page)
# ---------------------------------------------------------------------------

def _rank_demand_skills(have_skills: Set[str]) -> Tuple[List[Dict[str, Any]], int]:
    # Projected to skills_detected only — job_postings documents also carry
    # cached component_embeddings (matcher.py, ~40KB/doc across 4 vectors)
    # that this function never touches; fetching them here was pulling the
    # entire pool's embeddings over the network on every dashboard/market
    # trends load for no reason (measured ~18MB for 450 postings).
    postings = list(job_postings_collection.find({}, {"skills_detected": 1}))
    if not postings:
        return [], 0

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


def get_demand_skills(have_skills: Set[str], limit: int = 6) -> List[Dict[str, Any]]:
    """
    Public wrapper around _rank_demand_skills for callers outside this
    module (e.g. the Dashboard's "Skill demand in market" card) that just
    want the ranked list, not the total posting count.
    """
    demand_skills, _ = _rank_demand_skills(have_skills)
    return demand_skills[:limit]


def _demand_tier(score: int) -> str:
    if score >= 75:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


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
    return [{"name": s["name"], "demand": _demand_tier(s["score"])} for s in missing[:limit]]


def get_demand_and_missing_skills(
    have_skills: Set[str], demand_limit: int = 6, missing_limit: int = 6
) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """
    Combined variant for callers (dashboard_api.py) that need both the
    demand-ranked skill list AND this resume's missing-skill gap in the
    same request — computes _rank_demand_skills() (a full
    job_postings_collection scan) exactly once and derives both outputs
    from it, instead of calling get_demand_skills() and
    get_missing_skills_for_resume() separately, which each ran that same
    scan independently.
    """
    demand_skills, total = _rank_demand_skills(have_skills)
    if total == 0:
        return [], []

    missing = [s for s in demand_skills if not s["have"]]
    missing_skills = [{"name": s["name"], "demand": _demand_tier(s["score"])} for s in missing[:missing_limit]]
    return demand_skills[:demand_limit], missing_skills


# ---------------------------------------------------------------------------
# Market fit — how much of current demand a resume actually covers,
# weighted by how in-demand each skill is (not a flat skill count).
# ---------------------------------------------------------------------------

def _market_fit(demand_skills: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not demand_skills:
        return None
    total_weight = sum(s["score"] for s in demand_skills)
    if total_weight == 0:
        return None
    have_weight = sum(s["score"] for s in demand_skills if s["have"])
    score = round(have_weight / total_weight * 100)
    if score >= 75:
        label = "Strong"
    elif score >= 50:
        label = "Moderate"
    elif score >= 25:
        label = "Developing"
    else:
        label = "Needs work"
    return {"score": score, "label": label}


# ---------------------------------------------------------------------------
# Role demand + momentum — job title frequency, and its trend over time,
# computed from real posted_at/fetched_at timestamps. Titles are grouped by
# exact (lowercased) string — there's no role taxonomy in this app, so
# "Senior Backend Engineer" and "Backend Engineer II" are counted separately
# rather than guessing they're the same role.
# ---------------------------------------------------------------------------

def _posting_title_and_time(posting: Dict[str, Any]) -> Tuple[Optional[str], Optional[datetime]]:
    title = (posting.get("title") or "").strip()
    ts = posting.get("posted_at") or posting.get("fetched_at")
    return (title or None), ts


def _role_counts_in_window(
    postings: List[Dict[str, Any]], start: datetime, end: datetime
) -> Counter:
    counts: Counter = Counter()
    for posting in postings:
        title, ts = _posting_title_and_time(posting)
        if title and ts and start <= ts < end:
            counts[title.lower()] += 1
    return counts


def _role_demand_and_momentum(
    postings: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    display_title: Dict[str, str] = {}
    current_counts: Counter = Counter()
    timestamps: List[datetime] = []

    for posting in postings:
        title, ts = _posting_title_and_time(posting)
        if title:
            key = title.lower()
            current_counts[key] += 1
            display_title.setdefault(key, title)
        if ts:
            timestamps.append(ts)

    if not current_counts:
        return [], []

    role_demand = [
        {"title": display_title[key], "count": count, "trend": None}
        for key, count in current_counts.most_common(8)
    ]

    if not timestamps:
        return role_demand, []

    now = datetime.utcnow()
    oldest = min(timestamps)
    span_days = (now - oldest).total_seconds() / 86400
    if span_days < _MIN_TREND_SPAN_DAYS:
        return role_demand, []  # not enough history to call a trend, not a guess

    window_days = min(span_days / 2, _MAX_WINDOW_DAYS)
    window = timedelta(days=window_days)
    recent_start = now - window
    prior_start = now - (2 * window)

    recent_counts = _role_counts_in_window(postings, recent_start, now)
    prior_counts = _role_counts_in_window(postings, prior_start, recent_start)

    for row in role_demand:
        key = row["title"].lower()
        recent, prior = recent_counts.get(key, 0), prior_counts.get(key, 0)
        if prior == 0:
            row["trend"] = "new" if recent > 0 else None
            continue
        change = (recent - prior) / prior
        if change > 0.5:
            row["trend"] = "up2"
        elif change > 0.1:
            row["trend"] = "up"
        elif change < -0.1:
            row["trend"] = "down"
        else:
            row["trend"] = "flat"

    momentum = []
    for key, recent in recent_counts.items():
        prior = prior_counts.get(key, 0)
        if prior > 0 and recent > prior:
            pct = round((recent - prior) / prior * 100)
            momentum.append({"title": display_title.get(key, key), "pct_change": pct})

    momentum.sort(key=lambda m: -m["pct_change"])
    momentum = momentum[:5]
    max_pct = max((m["pct_change"] for m in momentum), default=0)
    for m in momentum:
        m["bar_pct"] = round(m["pct_change"] / max_pct * 100) if max_pct else 0

    return role_demand, momentum


# ---------------------------------------------------------------------------
# Career paths — the user's own top real job matches, deduped by title.
# Not a prediction model: literally "here are the highest-scoring distinct
# roles the AI Job Agent has actually matched you against."
# ---------------------------------------------------------------------------

def get_career_paths(user_id: str, limit: int = 3) -> List[Dict[str, Any]]:
    matches = list(
        job_matches_collection.find({"user_id": user_id}).sort("match_score", -1)
    )
    # One batched lookup instead of one find_one() per match — same fix as
    # dashboard_api.py and routes_agent.py below. Title-only projection:
    # this only ever reads job.get("title").
    job_ids = list({to_object_id(m["job_id"]) for m in matches})
    titles_by_id = {
        str(j["_id"]): j.get("title")
        for j in job_postings_collection.find({"_id": {"$in": job_ids}}, {"title": 1})
    }

    seen: Dict[str, int] = {}
    for match in matches:
        if len(seen) >= limit:
            break
        title = titles_by_id.get(match["job_id"])
        if not title or title in seen:
            continue
        seen[title] = match["match_score"]
    return [{"title": t, "score": s} for t, s in seen.items()]


# ---------------------------------------------------------------------------
# Insights callouts — the single biggest gap, and the fastest-rising role,
# each just a pointer into data already computed above.
# ---------------------------------------------------------------------------

def _insights(
    demand_skills: List[Dict[str, Any]], role_demand: List[Dict[str, Any]]
) -> Dict[str, Any]:
    top_gap = next((s for s in demand_skills if not s["have"]), None)
    rising = next((r for r in role_demand if r.get("trend") in ("up", "up2")), None)
    return {
        "top_gap": {"name": top_gap["name"], "demand": _demand_tier(top_gap["score"])} if top_gap else None,
        "rising": rising["title"] if rising else None,
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def get_market_trends_context(user_id: str) -> Dict[str, Any]:
    # Only title/posted_at/fetched_at are read below (_role_demand_and_momentum,
    # updated_at) — same reasoning as _rank_demand_skills' projection above.
    postings = list(job_postings_collection.find({}, {"title": 1, "posted_at": 1, "fetched_at": 1}))

    latest_analyses = list(
        analysis_collection.find({"user_id": user_id}).sort("analyzed_at", -1).limit(1)
    )
    have_skills = set()
    if latest_analyses:
        have_skills = {s.lower() for s in latest_analyses[0].get("matched_skills", [])}

    demand_skills, total = _rank_demand_skills(have_skills)
    role_demand, momentum = _role_demand_and_momentum(postings)

    fetch_times = [p.get("fetched_at") for p in postings if p.get("fetched_at")]
    updated_at = max(fetch_times) if fetch_times else None

    opportunity_skills = [
        {"name": s["name"], "demand": _demand_tier(s["score"])}
        for s in demand_skills if not s["have"]
    ][:5]

    return {
        "updated_at": updated_at,
        "postings_analyzed": total,
        "market_fit": _market_fit(demand_skills),
        "insights": _insights(demand_skills, role_demand),
        "demand_skills": demand_skills,
        "opportunity_skills": opportunity_skills,
        "role_demand": role_demand,
        "career_paths": get_career_paths(user_id),
        "momentum": momentum,
    }
