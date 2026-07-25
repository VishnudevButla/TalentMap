"""
app/step1_api/2_resume_analyze.py — Resume Analysis Route

Handles: POST /api/analyze

Flow:
1. Client sends { resume_id } in request body
2. Fetch the resume document from the DB to get the s3_key
3. Download the PDF bytes from S3
4. Run NLP pipeline:
   a. pdf_parser.py     → extract raw text from PDF
   b. preprocess.py     → clean text for NER
   c. ner_extractor.py  → extract skills, education, experience using Gemini
5. Save extracted entities to analysis_collection
6. Return structured results to client

There is no manual job-description input and no match score computed here.
Scoring is entirely the AI Job Agent's job: app/step4_agent/matcher.py
embeds these entities and scores them against real, live job postings on
every scan cycle — a resume is scored against many real jobs, not one
pasted-in JD. Predicted role and salary, and the dashboard's match-score
tile, are all derived from those real job matches — see
app/services/market_insights.py, served by GET /api/dashboard/summary.
"""

import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from bson import ObjectId

from app.core.db import resume_collection, analysis_collection, job_matches_collection
from app.core.s3_utils import download_file
from app.step2_nlp.pdf_parser_1 import extract_text
from app.step2_nlp.preprocess_2 import clean_text_for_ner
from app.step2_nlp.ner_extraction_3 import extract_entities
from app.schemas.result_schema import AnalysisResultResponse
from app.services.activity_log import log_activity

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    resume_id: str


# ---------------------------------------------------------------------------
# Main route
# ---------------------------------------------------------------------------

@router.post("/analyze", response_model=AnalysisResultResponse)
async def analyze_resume(req: AnalyzeRequest):
    resume_id = req.resume_id

    logger.info("Resume analysis started: resume_id=%s", resume_id)

    # ------------------------------------------------------------------
    # Step 1: Fetch resume doc
    # ------------------------------------------------------------------
    try:
        oid = ObjectId(resume_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid resume_id format.")

    resume_doc = resume_collection.find_one({"_id": oid})
    if not resume_doc:
        logger.warning("Resume not found: resume_id=%s", resume_id)
        raise HTTPException(status_code=404, detail="Resume not found.")

    s3_key = resume_doc.get("s3_key")
    if not s3_key:
        raise HTTPException(status_code=422, detail="S3 key not found for this resume.")

    try:
        # ------------------------------------------------------------------
        # Step 2: Download PDF from S3
        # ------------------------------------------------------------------
        file_bytes = download_file(s3_key)

        # ------------------------------------------------------------------
        # Step 3: Extract raw text
        # ------------------------------------------------------------------
        raw_text = extract_text(file_bytes)

        # ------------------------------------------------------------------
        # Step 4: Clean text and run NER
        # ------------------------------------------------------------------
        ner_text = clean_text_for_ner(raw_text)
        entities = extract_entities(resume_text=ner_text, job_description="")
        resume_skills: list = entities.get("skills", [])

        # ------------------------------------------------------------------
        # Step 5: Build result document
        # ------------------------------------------------------------------
        # No "match" here — there's no single JD to score against anymore.
        # The dashboard's match tile is derived from real job matches
        # instead, see app/services/market_insights.py.
        result_doc = {
            "resume_id": resume_id,
            "user_id": str(resume_doc.get("user_id", "")),
            "filename": resume_doc.get("filename", ""),
            "analyzed_at": datetime.utcnow(),
            "entities": entities,
            "matched_skills": resume_skills[:12],  # cap for display
            "missing_skills": [],  # see Market Trends page for real demand-based gaps
        }

        # ------------------------------------------------------------------
        # Step 6: Save to analysis_collection
        # ------------------------------------------------------------------
        insert_result = analysis_collection.insert_one(result_doc)
        result_doc["_id"] = str(insert_result.inserted_id)

        # Drop matches scored against a previous resume version so the
        # dashboard never shows stale scores while waiting for the next
        # agent scan cycle to recompute against this one.
        job_matches_collection.delete_many(
            {"user_id": result_doc["user_id"], "resume_id": {"$ne": resume_id}}
        )

        log_activity(
            user_id=result_doc["user_id"],
            type="analysis",
            message=f"Resume analyzed — {len(resume_skills)} skills extracted",
            icon="file",
            meta={"analysis_id": result_doc["_id"]},
        )
    except Exception:
        logger.exception("Resume analysis failed: resume_id=%s", resume_id)
        raise

    logger.info("Resume analysis completed: resume_id=%s", resume_id)

    # ------------------------------------------------------------------
    # Step 7: Return structured result to client
    # ------------------------------------------------------------------
    return result_doc
