"""
app/step4_agent/matcher.py — Resume ↔ Job Posting matching.

Real, no external credentials: reuses the same weighted cosine-similarity
approach as app/step1_api/resume_analyze_2.py (via
app/step2_nlp/embeddings_4.py) to score a user's latest resume analysis
against every stored job posting. Produces zero matches only because
job_postings_collection is empty until job_source_fetcher.py is wired to a
real source — this file itself is fully working.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

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
    description = job_doc.get("description", "") or job_doc.get("title", "")
    return {
        "skills": job_doc.get("skills_detected", []),
        "experience": [description],
        "projects": [description],
        "certifications": [description],
    }


def score_job_for_resume(resume_components: Dict[str, Any], job_doc: Dict[str, Any]) -> Dict[str, Any]:
    job_components = embed_components(_job_to_entities(job_doc))
    similarity_result = calculate_weighted_component_similarity(
        resume_components, job_components, DEFAULT_WEIGHTS
    )
    score = round(similarity_result["weighted_average_score"])
    return {
        "score": max(0, min(100, score)),
        "status": _status_for_score(score),
        "component_scores": similarity_result["individual_scores"],
    }


def run_matching_for_user(user_id: str) -> List[Dict[str, Any]]:
    latest = list(
        analysis_collection.find({"user_id": user_id}).sort("analyzed_at", -1).limit(1)
    )
    if not latest:
        return []

    latest_analysis = latest[0]
    resume_components = embed_components(latest_analysis.get("entities", {}))

    postings = list(job_postings_collection.find({}))
    logger.info("Matcher started: user_id=%s postings=%d", user_id, len(postings))
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
