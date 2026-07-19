"""
app/services/dashboard_data.py — Dashboard context builder.

The NLP/ML pipeline (app/step2_nlp, app/step3_ml) is not wired up yet, so
`get_sample_dashboard_context` returns realistic placeholder data shaped
exactly like a real analysis result. Once app/step1_api/2_resume_analyze.py
is implemented, replace the call in app/routers/pages.py with a function
that loads the stored result for the given user/resume and returns the
same shape.
"""

from typing import Any, Dict


def _salary_scale(axis_min: int, axis_max: int, market_min: int, market_max: int, median: int) -> Dict[str, float]:
    span = axis_max - axis_min
    return {
        "market_left_pct": round((market_min - axis_min) / span * 100, 1),
        "market_width_pct": round((market_max - market_min) / span * 100, 1),
        "marker_pct": round((median - axis_min) / span * 100, 1),
    }


def get_sample_dashboard_context(user_id: str) -> Dict[str, Any]:
    axis_min, axis_max = 80, 200
    market_min, market_max, median = 118, 165, 134

    return {
        "is_sample": True,
        "candidate": {
            "name": "Aditi Rao",
            "initials": "AR",
            "resume_filename": "Aditi_Rao_Resume.pdf",
            "analyzed_date": "Jul 19, 2026",
        },
        "target": {"role": "SDE-1", "company": "Amazon"},
        "match": {
            "score": 78,
            "status": "good",
            "status_label": "Strong match",
            "note": "Resume aligns closely with the <strong>SDE-1, Amazon</strong> posting "
                    "— ahead of 5 of 9 required skill areas.",
        },
        "predicted_role": {
            "title": "Backend Software Engineer",
            "confidence": 91,
            "alternates": ["Full-Stack Engineer", "Platform Engineer"],
        },
        "salary": {
            "median": median,
            "axis_min": axis_min,
            "axis_max": axis_max,
            "market_min": market_min,
            "market_max": market_max,
            **_salary_scale(axis_min, axis_max, market_min, market_max, median),
        },
        "matched_skills": [
            "Python", "REST APIs", "SQL", "AWS", "Docker", "Git",
            "Data Structures", "System Design basics",
        ],
        "missing_skills": [
            {"name": "Kubernetes", "demand": "high"},
            {"name": "Kafka", "demand": "high"},
            {"name": "GraphQL", "demand": "medium"},
            {"name": "Terraform", "demand": "medium"},
        ],
        "target_roles": [
            {"role": "SDE-1", "company": "Amazon", "location": "Seattle, WA · Full-time", "pct": 74, "status": "good", "link": "#"},
            {"role": "Platform Engineer", "company": "Datadog", "location": "New York, NY · Full-time", "pct": 68, "status": "good", "link": "#"},
            {"role": "Backend Engineer", "company": "Stripe", "location": "Remote (US) · Full-time", "pct": 61, "status": "warn", "link": "#"},
            {"role": "Software Engineer", "company": "Google", "location": "Mountain View, CA · Full-time", "pct": 52, "status": "warn", "link": "#"},
        ],
        "demand_skills": [
            {"name": "python", "score": 96, "have": True},
            {"name": "sql", "score": 90, "have": True},
            {"name": "aws", "score": 88, "have": True},
            {"name": "kubernetes", "score": 81, "have": False},
            {"name": "docker", "score": 74, "have": True},
            {"name": "kafka", "score": 58, "have": False},
        ],
    }