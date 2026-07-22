"""
app/step4_agent/job_source_fetcher.py — Job Board Source Fetcher

TODO(you): this is the integration point for a real job-board API or
scraper. Nothing here talks to the network yet — fetch_jobs_from_source()
always returns [] — so app/step4_agent/scheduler.py's run_scan_cycle()
runs end-to-end today but never finds any jobs. Wire one of:

  - Adzuna API        (https://developer.adzuna.com/)
  - JSearch/RapidAPI   (https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch)
  - Indeed Publisher API
  - USAJobs API
  - a scraper of your own

using `requests` (already a dependency) and settings.job_api_provider /
settings.job_api_key / settings.job_api_base_url from app/config.py.

Each returned dict should be shaped like a JobPosting so it can be passed
straight to app.core.db.job_postings_collection.update_one(..., upsert=True):

{
    "source": str, "external_id": str, "title": str, "company": str,
    "company_logo_url": Optional[str], "location": str,
    "remote_type": "onsite" | "remote" | "hybrid", "description": str,
    "url": str, "skills_detected": List[str],
    "salary_min": Optional[float], "salary_max": Optional[float],
    "posted_at": datetime,
}
"""

from typing import Any, Dict, List

from app.config import settings


def fetch_jobs_from_source(source: str, keywords: List[str]) -> List[Dict[str, Any]]:
    if not settings.job_api_key:
        print(f"[job_source_fetcher] No job_api_key configured — skipping source '{source}'.")
        return []

    # TODO(you): call the real API here using settings.job_api_provider /
    # settings.job_api_key / settings.job_api_base_url, and map its response
    # into the JobPosting shape documented above.
    return []
