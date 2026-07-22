"""
app/services/market_insights.py — Predicted role & salary, derived from
real job matches.

Replaces the old MLPredictor placeholder (app/step3_ml, deleted — it was a
non-functional stub with no trained model). Instead of a hardcoded
classifier/regressor, this reads the user's top-ranked entries in
job_matches_collection, joins to job_postings_collection for title/salary,
and derives a predicted role + salary band from them.

Returns None when there's nothing to derive from yet (no job matches) —
callers should render an explicit empty state, not a fabricated number.
"""

from typing import Any, Dict, Optional

from app.core.db import job_matches_collection, job_postings_collection, to_object_id


def get_predicted_role_and_salary(user_id: str, top_n: int = 5) -> Optional[Dict[str, Any]]:
    matches = list(
        job_matches_collection.find({"user_id": user_id}).sort("match_score", -1).limit(top_n)
    )
    if not matches:
        return None

    # Join each match to its posting; skip any whose posting has since been removed.
    postings = []
    for match in matches:
        job = job_postings_collection.find_one({"_id": to_object_id(match["job_id"])})
        if job:
            postings.append((match, job))

    if not postings:
        return None

    top_match, top_job = postings[0]
    top_title = top_job.get("title")
    if not top_title:
        return None

    alternates = []
    for _, job in postings[1:]:
        title = job.get("title")
        if title and title != top_title and title not in alternates:
            alternates.append(title)

    predicted_role = {
        "title": top_title,
        "confidence": top_match["match_score"],  # a real match score, not a fixed placeholder
        "alternates": alternates[:3],
    }

    salary_points = []
    for _, job in postings:
        for value in (job.get("salary_min"), job.get("salary_max")):
            if value is not None:
                salary_points.append(value)

    salary = None
    if salary_points:
        market_min = round(min(salary_points) / 1000)
        market_max = round(max(salary_points) / 1000)
        padding = max(10, round((market_max - market_min) * 0.25))
        axis_min = max(0, market_min - padding)
        axis_max = market_max + padding
        median = round((market_min + market_max) / 2)

        # Same left/width/marker-as-percent-of-axis convention as
        # app/services/dashboard_data.py's _salary_scale, so the band chart
        # renders identically whether it's sample or real data.
        span = axis_max - axis_min
        salary = {
            "median": median,
            "axis_min": axis_min,
            "axis_max": axis_max,
            "market_min": market_min,
            "market_max": market_max,
            "market_left_pct": round((market_min - axis_min) / span * 100, 1),
            "market_width_pct": round((market_max - market_min) / span * 100, 1),
            "marker_pct": round((median - axis_min) / span * 100, 1),
        }

    return {"predicted_role": predicted_role, "salary": salary}
