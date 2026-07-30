"""
app/step4_agent/matcher.py — Resume ↔ Job Posting matching.

Real, no external credentials: reuses the same weighted cosine-similarity
approach as app/step1_api/resume_analyze_2.py (via
app/step2_nlp/embeddings_4.py) to score a user's latest resume analysis
against stored job postings. Produces zero matches only because
job_postings_collection is empty until job_source_fetcher.py is wired to a
real source — this file itself is fully working.

Two performance properties that matter as the pool/user base grows:
- Job embeddings are cached on the job_postings document the first time a
  job is ever scored (component_embeddings) and reused after that — a
  job's text never changes post-fetch, so re-running the sentence
  transformer on it every cycle for every user was pure waste.
- run_matching_for_user(user_id, since=...) can be scoped to only postings
  first seen after `since`, so a scheduled cycle only scores genuinely new
  postings instead of re-listing the entire pool every time. Pass
  since=None (the default) for a full pass — required the first time a
  user is scanned, and for a brand-new resume version, since neither has
  any prior matches to build on incrementally.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

from app.core.db import analysis_collection, job_postings_collection, job_matches_collection
from app.services.activity_log import log_activity
from app.step2_nlp.embeddings_4 import embed_components, calculate_weighted_component_similarity, DEFAULT_WEIGHTS

logger = logging.getLogger(__name__)


def _status_for_score(score: int) -> str:
    if score >= 85:
        return "excellent"
    if score >= 70:
        return "good"
    if score >= 45:
        return "warn"
    return "crit"


def _job_to_entities(job_doc: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Reads the structured job_entities dict (app/step4_agent/
    job_entity_extractor.py, populated at fetch time by
    job_source_fetcher.py) — never the raw description. Older postings
    fetched before that extractor existed won't have job_entities yet;
    entities defaults to {} for those, meaning every component below comes
    back empty and the honest-missing-data scoring in
    calculate_weighted_component_similarity() correctly excludes them
    rather than penalizing to 0.
    """
    entities = job_doc.get("job_entities") or {}
    return {
        "skills": job_doc.get("skills_detected", []),
        "experience": entities.get("experience_requirements", []),
        "education": entities.get("education_requirements", []),
        "certifications": entities.get("certifications", []),
    }


def _get_job_components(job_doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns this job's component embeddings, computing and caching them on
    the job_postings document the first time this job is ever scored.
    Every subsequent score — this cycle, any future cycle, any user — reads
    the cache instead of re-running the sentence transformer.
    """
    cached = job_doc.get("component_embeddings")
    if cached:
        return {key: np.array(vector) for key, vector in cached.items()}

    job_components = embed_components(_job_to_entities(job_doc))
    job_postings_collection.update_one(
        {"_id": job_doc["_id"]},
        {"$set": {"component_embeddings": {k: v.tolist() for k, v in job_components.items()}}},
    )
    return job_components


def score_job_for_resume(resume_components: Dict[str, Any], job_doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Returns None when literally nothing was comparable between this resume
    and this job (every component absent on one side or the other) —
    honest "no data" rather than a fabricated 0%. Callers should skip
    creating a match in that case, same as any other "not enough real
    data yet" state elsewhere in this codebase.
    """
    job_components = _get_job_components(job_doc)
    similarity_result = calculate_weighted_component_similarity(
        resume_components, job_components, DEFAULT_WEIGHTS
    )
    raw_score = similarity_result["weighted_average_score"]
    if raw_score is None:
        return None

    score = round(raw_score)
    return {
        "score": max(0, min(100, score)),
        "status": _status_for_score(score),
        "component_scores": similarity_result["individual_scores"],
    }


def run_matching_for_user(user_id: str, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """
    since=None scores against the entire pool — required for a user's very
    first scan and for a brand-new resume version, since neither has any
    prior matches to build on. Pass since=<a user's last scan time> to
    score only postings first seen after that (see job_source_fetcher.py's
    created_at, set once on insert and never touched again).
    """
    latest = list(
        analysis_collection.find({"user_id": user_id}).sort("analyzed_at", -1).limit(1)
    )
    if not latest:
        return []

    latest_analysis = latest[0]
    resume_components = embed_components(latest_analysis.get("entities", {}))

    query = {"created_at": {"$gt": since}} if since else {}
    postings = list(job_postings_collection.find(query))
    logger.info("Matcher started: user_id=%s postings=%d since=%s", user_id, len(postings), since)
    new_matches = []

    resume_id = latest_analysis.get("resume_id")

    for job_doc in postings:
        job_id = str(job_doc["_id"])
        # Keyed on resume_id too, so a new resume version is rescored
        # against every posting instead of being silently skipped.
        existing = job_matches_collection.find_one(
            {"user_id": user_id, "job_id": job_id, "resume_id": resume_id}
        )
        if existing:
            continue  # already scored this posting for this resume version

        result = score_job_for_resume(resume_components, job_doc)
        if result is None:
            continue  # nothing comparable between this resume and this job — no fabricated match

        match_doc = {
            "user_id": user_id,
            "job_id": job_id,
            "resume_id": resume_id,
            "match_score": result["score"],
            "status": result["status"],
            "component_scores": result["component_scores"],
            "applied": False,
            "applied_at": None,
            "seen": False,
            "created_at": datetime.utcnow(),
        }
        # Upsert on the same (user_id, job_id, resume_id) key as the unique
        # index in db.py — makes a concurrent scan-now/scheduled overlap
        # structurally unable to double-insert, rather than just unlikely.
        job_matches_collection.update_one(
            {"user_id": user_id, "job_id": job_id, "resume_id": resume_id},
            {"$setOnInsert": match_doc},
            upsert=True,
        )
        new_matches.append(match_doc)

        if result["score"] >= 70:
            log_activity(
                user_id=user_id,
                type="job_match",
                message=f"New match: {job_doc.get('title', 'Role')} at {job_doc.get('company', 'a company')} — {result['score']}%",
                icon="briefcase",
                meta={"job_id": job_id, "match_score": result["score"]},
            )

    logger.info("Matcher completed: user_id=%s new_matches=%d", user_id, len(new_matches))
    return new_matches
