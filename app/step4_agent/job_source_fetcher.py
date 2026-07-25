"""
app/step4_agent/job_source_fetcher.py — Job Board Source Fetcher

Fetches real job postings from two fully free, officially sanctioned sources:

  - Adzuna API    (https://developer.adzuna.com/)   — needs APP_ID + APP_KEY
  - RemoteOK API  (https://remoteok.com/api)        — no auth, public endpoint

Every job returned by either fetcher is normalised into the same dict shape
so that scheduler.py's _upsert_postings() and matcher.py's score_job_for_resume()
can treat all jobs identically regardless of source:

{
    "source":       str,                 # "adzuna" | "remoteok"
    "external_id":  str,                 # unique ID from that source (for dedup)
    "title":        str,
    "company":      str,
    "description":  str,                 # full JD text — used by embeddings_4.py
    "location":     str,
    "remote_type":  str,                 # "remote" | "onsite" | "hybrid"
    "url":          str,                 # direct application / listing link
    "skills_detected": List[str],        # populated by run_job_fetch_cycle()
    "salary_min":   Optional[float],
    "salary_max":   Optional[float],
    "posted_at":    datetime,
}

Public entry points:
  fetch_jobs_from_source(source, keywords)  — called by scheduler.py per source
  run_job_fetch_cycle()                     — full orchestration: fetch → save
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from app.config import settings
from app.core.db import job_postings_collection, analysis_collection

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# The real, currently-wired sources — run_job_fetch_cycle() calls both of
# these unconditionally every cycle. Single source of truth for anywhere
# that needs to display "sources monitored" (state.py, routes_agent.py).
SOURCES = ["adzuna", "remoteok"]

# RemoteOK blocks the default python-requests User-Agent with a 403.
_REMOTEOK_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# Number of results to request per Adzuna page (max 50).
_ADZUNA_RESULTS_PER_PAGE = 10

# Polite delay between API calls (seconds) to avoid hammering rate limits.
_REQUEST_DELAY_SEC = 0.5


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_remote(title: str, description: str) -> bool:
    """Checks for common remote-work signals in the title or description."""
    text = (title + " " + description).lower()
    return any(kw in text for kw in ("remote", "work from home", "wfh", "distributed", "anywhere"))


def _parse_datetime(raw: Optional[str]) -> datetime:
    """
    Converts an ISO-8601 string to a timezone-aware UTC datetime.
    Falls back to now() if parsing fails.
    """
    if not raw:
        return datetime.now(tz=timezone.utc)
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return datetime.now(tz=timezone.utc)


# ---------------------------------------------------------------------------
# Adzuna Fetcher
# ---------------------------------------------------------------------------

def fetch_adzuna_jobs(
    query: str,
    country_code: str = "us",
    page: int = 1,
) -> List[Dict[str, Any]]:
    """
    Calls the Adzuna job search API and returns jobs normalised to the common schema.

    Args:
        query:        Free-text job search query, e.g. "software engineer".
        country_code: Two-letter country code supported by Adzuna (default: "us").
        page:         Pagination page number (1-indexed).

    Returns:
        List of normalised job dicts, or [] on any error.
    """
    url = f"{settings.ADZUNA_BASE_URL}/jobs/{country_code}/search/{page}"
    params = {
        "app_id": settings.ADZUNA_APP_ID,
        "app_key": settings.ADZUNA_APP_KEY,
        "results_per_page": _ADZUNA_RESULTS_PER_PAGE,
        "what": query,
        "content-type": "application/json",
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as exc:
        logger.warning("Adzuna API request failed: query=%s error=%s", query, exc)
        return []

    results = []
    for raw in data.get("results", []):
        title = raw.get("title", "")
        description = raw.get("description", "")
        results.append({
            "source": "adzuna",
            "external_id": str(raw.get("id", "")),
            "title": title,
            "company": raw.get("company", {}).get("display_name", ""),
            "description": description,
            "location": raw.get("location", {}).get("display_name", ""),
            "remote_type": "remote" if _is_remote(title, description) else "onsite",
            "url": raw.get("redirect_url", ""),
            "skills_detected": [],                   # populated by run_job_fetch_cycle
            "salary_min": raw.get("salary_min"),
            "salary_max": raw.get("salary_max"),
            "posted_at": _parse_datetime(raw.get("created")),
        })

    logger.info(
        "Adzuna fetch complete: query=%r country=%s page=%d jobs_returned=%d",
        query, country_code, page, len(results),
    )
    return results


# ---------------------------------------------------------------------------
# RemoteOK Fetcher
# ---------------------------------------------------------------------------

def fetch_remoteok_jobs() -> List[Dict[str, Any]]:
    """
    Calls the public RemoteOK API and returns jobs normalised to the common schema.

    RemoteOK requires no authentication. The first element of the JSON array
    is always a legal disclaimer object — it is skipped automatically.

    Returns:
        List of normalised job dicts, or [] on any error.
    """
    try:
        response = requests.get(
            settings.REMOTEOK_BASE_URL,
            headers=_REMOTEOK_HEADERS,
            timeout=15,
        )
        response.raise_for_status()
        raw_list = response.json()
    except requests.exceptions.RequestException as exc:
        logger.warning("RemoteOK API request failed: error=%s", exc)
        return []

    # RemoteOK always puts a legal notice dict as the first element.
    if raw_list and isinstance(raw_list[0], dict) and "legal" in str(raw_list[0]).lower():
        raw_list = raw_list[1:]

    results = []
    for raw in raw_list:
        if not isinstance(raw, dict):
            continue

        title = raw.get("position", "")
        description = raw.get("description", "")

        # salary fields may be integers or strings — coerce safely
        def _to_float(val) -> Optional[float]:
            try:
                return float(val) if val not in (None, "", 0) else None
            except (TypeError, ValueError):
                return None

        results.append({
            "source": "remoteok",
            "external_id": str(raw.get("id", raw.get("slug", ""))),
            "title": title,
            "company": raw.get("company", ""),
            "description": description,
            "location": raw.get("location", "Remote"),
            "remote_type": "remote",               # RemoteOK is 100 % remote
            "url": raw.get("url", f"https://remoteok.com/remote-jobs/{raw.get('slug', '')}"),
            "skills_detected": raw.get("tags", []),  # RemoteOK provides skill tags
            "salary_min": _to_float(raw.get("salary_min")),
            "salary_max": _to_float(raw.get("salary_max")),
            "posted_at": _parse_datetime(raw.get("date")),
        })

    logger.info("RemoteOK fetch complete: jobs_returned=%d", len(results))
    return results


# ---------------------------------------------------------------------------
# MongoDB save (deduplication via upsert)
# ---------------------------------------------------------------------------

def save_new_jobs(jobs: List[Dict[str, Any]]) -> int:
    """
    Upserts job documents into job_postings_collection using (source, external_id)
    as the unique key. Returns the number of newly inserted or updated records.

    A MongoDB unique compound index on {source: 1, external_id: 1} should exist
    to enforce deduplication at the DB level — create it once with:

        job_postings_collection.create_index(
            [("source", 1), ("external_id", 1)], unique=True
        )
    """
    if not jobs:
        return 0

    saved = 0
    for job in jobs:
        try:
            result = job_postings_collection.update_one(
                {
                    "source": job["source"],
                    "external_id": job["external_id"],
                },
                {"$set": {**job, "fetched_at": datetime.now(tz=timezone.utc)}},
                upsert=True,
            )
            if result.upserted_id or result.modified_count > 0:
                saved += 1
        except Exception as exc:
            logger.warning(
                "Failed to save job: source=%s external_id=%s error=%s",
                job.get("source"), job.get("external_id"), exc,
            )

    return saved


# ---------------------------------------------------------------------------
# Demand-driven query derivation
# ---------------------------------------------------------------------------

def get_search_queries(fallback: Optional[List[str]] = None) -> List[str]:
    """
    Derives search queries from the job titles / skills found in users' most
    recent resume analyses (demand-driven approach), so Adzuna's monthly API
    quota is spent on terms that are actually relevant to your user base.

    Falls back to a fixed list if the analyses collection is empty or unavailable.
    """
    fallback = fallback or [
        "software engineer",
        "data analyst",
        "machine learning engineer",
        "backend developer",
        "product manager",
    ]

    try:
        # Pull distinct top-level experience entries used as title proxies.
        # Limit to 5 so we don't blow the Adzuna free-tier quota in one cycle.
        titles = analysis_collection.distinct("entities.experience")
        queries = [t for t in titles if isinstance(t, str) and t.strip()][:5]
        return queries if queries else fallback
    except Exception as exc:
        logger.warning("Could not derive search queries from analyses: %s", exc)
        return fallback


# ---------------------------------------------------------------------------
# Main orchestration entry point (called by run_scan_cycle in scheduler.py)
# ---------------------------------------------------------------------------

def run_job_fetch_cycle(queries: Optional[List[str]] = None) -> Dict[str, int]:
    """
    Full fetch-and-save cycle:
      1. Fetches RemoteOK jobs (no quota cost, always run).
      2. Fetches Adzuna jobs for each derived or provided query.
      3. Saves all results to MongoDB with deduplication.

    Returns a summary dict: {"fetched": N, "saved": M}.
    """
    queries = queries or get_search_queries()
    all_jobs: List[Dict[str, Any]] = []

    # --- RemoteOK (no quota, fetch once per cycle) ---
    logger.info("Starting RemoteOK fetch...")
    all_jobs.extend(fetch_remoteok_jobs())
    time.sleep(_REQUEST_DELAY_SEC)

    # --- Adzuna (one call per query; conserve the monthly free quota) ---
    logger.info("Starting Adzuna fetch: %d queries", len(queries))
    for query in queries:
        all_jobs.extend(fetch_adzuna_jobs(query=query))
        time.sleep(_REQUEST_DELAY_SEC)

    saved = save_new_jobs(all_jobs)
    logger.info(
        "Job fetch cycle complete: fetched=%d saved_or_updated=%d",
        len(all_jobs), saved,
    )
    return {"fetched": len(all_jobs), "saved": saved}


# ---------------------------------------------------------------------------
# Legacy shim — keeps scheduler.py's existing call-site working unchanged
# ---------------------------------------------------------------------------

def fetch_jobs_from_source(source: str, keywords: List[str]) -> List[Dict[str, Any]]:
    """
    Adapter used by scheduler.py's run_scan_cycle() loop.
    Routes to the correct source fetcher based on the `source` argument.

    Args:
        source:   "adzuna", "remoteok", or "default" (runs both).
        keywords: Search keywords for Adzuna; ignored for RemoteOK.
    """
    source = source.strip().lower()

    if source in ("adzuna",):
        query = keywords[0] if keywords else "software engineer"
        return fetch_adzuna_jobs(query=query)

    if source in ("remoteok",):
        return fetch_remoteok_jobs()

    # "default" or any unknown value — run both
    jobs: List[Dict[str, Any]] = []
    jobs.extend(fetch_remoteok_jobs())
    if keywords:
        jobs.extend(fetch_adzuna_jobs(query=keywords[0]))
    return jobs
