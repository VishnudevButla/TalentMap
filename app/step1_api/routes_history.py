"""
app/step1_api/routes_history.py — Resume History Routes

Handles: GET /api/history, GET /api/resumes/{resume_id}/download,
DELETE /api/resumes/{resume_id}

Flow (GET /api/history):
1. Identify the caller via the JWT (Depends(get_current_user)) — never a
   trusted user_id from the URL, matching upload_resume_1.py's pattern.
2. Query resume_collection for every resume the user has ever uploaded —
   this is the source of truth for "my resumes," not analysis_collection,
   since a resume can exist without having been analyzed (yet).
3. For each resume, attach its latest analysis's extracted skills, its
   current real job-match score (scoped to that specific resume version —
   see app/services/market_insights.py), a demand-ranked skill gap (see
   app/services/market_trends_data.py), and is_active — set by
   upload_resume_1.py so exactly one resume per user is "current"
   (uploading always replaces; there's no "keep two active" concept).
4. Return one card's worth of metadata per resume, most recent first.

GET /api/resumes/{resume_id}/download issues a fresh short-lived S3
presigned URL on request rather than embedding one in the list response
above, so it never goes stale between page load and click.

DELETE /api/resumes/{resume_id} removes the resume itself, not just a
flag — the S3 object, the resume_collection doc, and this resume
version's own analysis + job_matches docs (a match scored against a
resume that no longer exists would just be a dangling, unexplainable
number). It does NOT touch any other resume version's analyses/matches,
so deleting one old resume never breaks the current one. If the deleted
resume was active, the next most recent surviving resume (if any)
becomes active — never left with two actives or a silently-stale one.
"""

import logging

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.db import resume_collection, analysis_collection, job_matches_collection
from app.core.security import get_current_user
from app.core.s3_utils import get_presigned_url, delete_file
from app.services.market_insights import get_match_summary_for_resume
from app.services.market_trends_data import get_missing_skills_for_resume

logger = logging.getLogger(__name__)

router = APIRouter()


class RenameRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=200)


@router.get("/history")
async def get_history(user_id: str = Depends(get_current_user), skip: int = 0, limit: int = 20):
    resumes = list(
        resume_collection.find({"user_id": user_id})
        .sort("_id", -1)
        .skip(skip)
        .limit(limit)
    )

    # Pagination-independent — computed from the whole collection, not the
    # skip/limit slice below, so stats stay correct once a user has more
    # than one page of resumes (and the active resume, always the newest,
    # would otherwise silently vanish from "has_active_resume" on page 2+).
    total_resumes = resume_collection.count_documents({"user_id": user_id})

    results = []
    active_stats = None
    for r in resumes:
        resume_id = str(r["_id"])
        analysis = analysis_collection.find_one(
            {"resume_id": resume_id}, sort=[("analyzed_at", -1)]
        )
        # Older resumes predate the uploaded_at field — ObjectId encodes
        # its own creation time, so it's a safe fallback either way.
        uploaded_at = r.get("uploaded_at") or r["_id"].generation_time
        is_active = r.get("is_active", False)
        entities = analysis.get("entities") if analysis else None
        match = get_match_summary_for_resume(resume_id)
        skills_count = len(entities.get("skills", [])) if entities else 0

        results.append({
            "resume_id": resume_id,
            "filename": r.get("filename", "resume.pdf"),
            "uploaded_at": uploaded_at,
            "analyzed_at": analysis.get("analyzed_at") if analysis else None,
            # Resumes uploaded before this field existed have no is_active
            # key at all — default them to False (not "current") rather
            # than guessing at load time. A one-off migration (run once,
            # not app code) promotes each user's actual most-recent
            # pre-existing resume to True so this isn't permanently blank.
            "is_active": is_active,
            "matched_skills": analysis.get("matched_skills", []) if analysis else [],
            "missing_skills": get_missing_skills_for_resume(resume_id) if analysis else [],
            # Per-category counts — the History page shows these as chips
            # without needing to ship the full entity lists just to count them.
            "entity_counts": {
                "skills": skills_count,
                "education": len(entities.get("education", [])) if entities else 0,
                "experience": len(entities.get("experience", [])) if entities else 0,
                "projects": len(entities.get("projects", [])) if entities else 0,
                "certifications": len(entities.get("certifications", [])) if entities else 0,
            },
            # Full NER breakdown — skills/education/experience/projects/
            # certifications — the same structured entities embeddings_4.py
            # turns into vectors for matching. Shown as-is on the History
            # page so a user can see exactly what was parsed from a given
            # resume version.
            "entities": entities,
            "match": match,
        })

        if is_active:
            active_stats = {"match": match, "skills_count": skills_count}

    # The active resume is always the newest, so it's on page 1 in the
    # common case (skip=0) and already computed above — only fall back to
    # a direct lookup on a deeper page, so pagination never has to pay for
    # this on every request.
    if active_stats is None and skip > 0:
        active_resume = resume_collection.find_one({"user_id": user_id, "is_active": True})
        if active_resume:
            active_resume_id = str(active_resume["_id"])
            active_analysis = analysis_collection.find_one(
                {"resume_id": active_resume_id}, sort=[("analyzed_at", -1)]
            )
            active_entities = active_analysis.get("entities") if active_analysis else None
            active_stats = {
                "match": get_match_summary_for_resume(active_resume_id),
                "skills_count": len(active_entities.get("skills", [])) if active_entities else 0,
            }

    # Summary row at the top of the page — derived entirely from the active
    # resume (or honestly empty/None if there isn't one): no resume
    # currently active means no stats to show, not a fabricated zero
    # pretending everything's fine. total_resumes is the real collection
    # count, not len(results) — stays correct once results is a paginated
    # slice.
    stats = {
        "total_resumes": total_resumes,
        "has_active_resume": active_stats is not None,
        "best_match_score": active_stats["match"]["score"] if active_stats and active_stats["match"] else None,
        "skills_extracted": active_stats["skills_count"] if active_stats else 0,
    }

    return {"user_id": user_id, "count": len(results), "results": results, "stats": stats}


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


@router.patch("/resumes/{resume_id}/rename")
async def rename_resume(resume_id: str, body: RenameRequest, user_id: str = Depends(get_current_user)):
    try:
        oid = ObjectId(resume_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid resume_id format.")

    result = resume_collection.update_one(
        {"_id": oid, "user_id": user_id},
        {"$set": {"filename": body.filename.strip()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Resume not found.")

    return {"resume_id": resume_id, "filename": body.filename.strip()}


@router.delete("/resumes/{resume_id}")
async def delete_resume(resume_id: str, user_id: str = Depends(get_current_user)):
    try:
        oid = ObjectId(resume_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid resume_id format.")

    # Scoped to the caller's own user_id — never let one user delete
    # another's resume by guessing an id.
    resume = resume_collection.find_one({"_id": oid, "user_id": user_id})
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found.")

    try:
        delete_file(resume["s3_key"])
    except Exception:
        # A leaked S3 object is a minor storage cost, not a correctness
        # issue — don't block the user from removing the resume from
        # their account just because S3 is having a bad moment.
        logger.warning("S3 delete failed, continuing with DB cleanup: resume_id=%s", resume_id, exc_info=True)

    resume_collection.delete_one({"_id": oid})
    # This resume version's own analysis + matches only — never touches
    # any other resume's history, so deleting an old version can't break
    # the current one.
    analysis_collection.delete_many({"resume_id": resume_id})
    job_matches_collection.delete_many({"resume_id": resume_id})

    if resume.get("is_active"):
        next_resume = resume_collection.find_one(
            {"user_id": user_id}, sort=[("_id", -1)]
        )
        if next_resume:
            resume_collection.update_one(
                {"_id": next_resume["_id"]}, {"$set": {"is_active": True}}
            )

    logger.info("Resume deleted: user_id=%s resume_id=%s", user_id, resume_id)
    return {"deleted": True, "resume_id": resume_id}
