"""
app/step1_api/routes_history.py — Resume History Routes

Handles: GET /api/history, GET /api/resumes/{resume_id}/download

Flow (GET /api/history):
1. Identify the caller via the JWT (Depends(get_current_user)) — never a
   trusted user_id from the URL, matching upload_resume_1.py's pattern.
2. Query resume_collection for every resume the user has ever uploaded —
   this is the source of truth for "my resumes," not analysis_collection,
   since a resume can exist without having been analyzed (yet).
3. For each resume, attach its latest analysis's extracted skills, its
   current real job-match score (scoped to that specific resume version —
   see app/services/market_insights.py), and a demand-ranked skill gap
   (see app/services/market_trends_data.py).
4. Return one card's worth of metadata per resume, most recent first.

GET /api/resumes/{resume_id}/download issues a fresh short-lived S3
presigned URL on request rather than embedding one in the list response
above, so it never goes stale between page load and click.
"""

import logging

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from app.core.db import resume_collection, analysis_collection
from app.core.security import get_current_user
from app.core.s3_utils import get_presigned_url
from app.services.market_insights import get_match_summary_for_resume
from app.services.market_trends_data import get_missing_skills_for_resume

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/history")
async def get_history(user_id: str = Depends(get_current_user), skip: int = 0, limit: int = 20):
    resumes = list(
        resume_collection.find({"user_id": user_id})
        .sort("_id", -1)
        .skip(skip)
        .limit(limit)
    )

    results = []
    for r in resumes:
        resume_id = str(r["_id"])
        analysis = analysis_collection.find_one(
            {"resume_id": resume_id}, sort=[("analyzed_at", -1)]
        )
        # Older resumes predate the uploaded_at field — ObjectId encodes
        # its own creation time, so it's a safe fallback either way.
        uploaded_at = r.get("uploaded_at") or r["_id"].generation_time

        results.append({
            "resume_id": resume_id,
            "filename": r.get("filename", "resume.pdf"),
            "uploaded_at": uploaded_at,
            "matched_skills": analysis.get("matched_skills", []) if analysis else [],
            "missing_skills": get_missing_skills_for_resume(resume_id) if analysis else [],
            "match": get_match_summary_for_resume(resume_id),
        })

    return {"user_id": user_id, "count": len(results), "results": results}


@router.get("/resumes/{resume_id}/download")
async def download_resume(resume_id: str, user_id: str = Depends(get_current_user)):
    try:
        oid = ObjectId(resume_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid resume_id format.")

    # Scoped to the caller's own user_id — never let one user fetch
    # another's resume by guessing an id.
    resume = resume_collection.find_one({"_id": oid, "user_id": user_id})
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found.")

    try:
        url = get_presigned_url(resume["s3_key"])
    except Exception:
        logger.exception("Failed to generate download URL: resume_id=%s", resume_id)
        raise HTTPException(status_code=502, detail="Could not generate a download link right now.")

    return {"url": url, "filename": resume.get("filename", "resume.pdf")}
