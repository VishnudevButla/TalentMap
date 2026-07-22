"""
app/services/dashboard_data.py — Dashboard context builder.

`get_sample_dashboard_context` returns illustrative placeholder data,
shaped like a real dashboard payload, for the server-rendered pre-hydration
state (see templates/dashboard.html). Real values are fetched client-side
from GET /api/dashboard/summary (app/routers/dashboard_api.py) and swap
these in — see static/js/dashboard.js's hydrateFromSummary(). Note:
predicted_role/salary below are just illustrative sample numbers, not ML
output — the real equivalents are derived from actual job matches by
app/services/market_insights.py.
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
        "ai_jobs_found_today": 17,
        "ai_jobs_found_delta": "+5 new since last scan",
        "job_matches": [
            {"title": "SDE-1 - Backend Engineer", "company": "Amazon", "location": "Seattle, WA", "work_type": "Full-time", "remote_type": "onsite", "match_score": 94, "status": "excellent", "posted": "2h ago", "url": "#"},
            {"title": "Software Engineer", "company": "Google", "location": "Mountain View, CA", "work_type": "Full-time", "remote_type": "onsite", "match_score": 91, "status": "excellent", "posted": "5h ago", "url": "#"},
            {"title": "Platform Engineer", "company": "Datadog", "location": "New York, NY", "work_type": "Full-time", "remote_type": "onsite", "match_score": 88, "status": "good", "posted": "8h ago", "url": "#"},
            {"title": "Backend Developer", "company": "NVIDIA", "location": "Remote", "work_type": "Full-time", "remote_type": "remote", "match_score": 87, "status": "good", "posted": "10h ago", "url": "#"},
        ],
        "agent": {
            "is_active": True,
            "next_scan_in_seconds": 6495,
            "jobs_scanned_today": 1462,
            "new_matches_today": 14,
            "emails_sent_today": 5,
            "sources_monitored": 7,
        },
        "activity": [
            {"icon": "mail", "message": "Email alert sent — 5 new high match jobs", "time": "2h ago"},
            {"icon": "briefcase", "message": "New matches found — 14 job matches added", "time": "3h ago"},
            {"icon": "file", "message": "Resume analyzed — Score improved by 12%", "time": "1d ago"},
            {"icon": "mail", "message": "Email alert sent — 8 new high match jobs", "time": "1d ago"},
        ],
    }