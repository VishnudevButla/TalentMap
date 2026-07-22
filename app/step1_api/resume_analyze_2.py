"""
app/step1_api/2_resume_analyze.py — Resume Analysis Route

Handles: POST /api/analyze

Flow:
1. Client sends { resume_id, job_description } in request body
2. Fetch the resume document from the DB to get the s3_key
3. Download the PDF bytes from S3
4. Run NLP pipeline:
   a. pdf_parser.py     → extract raw text from PDF
   b. preprocess.py     → clean text for embeddings (and NER-safe version)
   c. ner_extractor.py  → extract skills, education, experience using Gemini
   d. embeddings.py     → generate vector embeddings for similarity scoring
5. Compute match score via weighted cosine similarity
6. Save analysis results to analysis_collection
7. Return structured results to client

Predicted role and salary are NOT computed here — they're derived from the
user's real, ranked job matches instead. See
app/services/market_insights.py, served by GET /api/dashboard/summary.
"""

from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from bson import ObjectId

from app.core.db import resume_collection, analysis_collection
from app.core.s3_utils import download_file
from app.step2_nlp.pdf_parser_1 import extract_text
from app.step2_nlp.preprocess_2 import clean_text, clean_text_for_ner
from app.step2_nlp.ner_extraction_3 import extract_entities
from app.step2_nlp.embeddings_4 import (
    embed_components,
    get_embedding,
    calculate_weighted_component_similarity,
    DEFAULT_WEIGHTS,
)
from app.schemas.result_schema import AnalysisResultResponse
from app.services.activity_log import log_activity

router = APIRouter()

# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    resume_id: str
    job_description: str = ""


# ---------------------------------------------------------------------------
# Helper: build a job-description entity dict (mirrors resume entity shape)
# ---------------------------------------------------------------------------

def _jd_to_entities(job_description: str) -> dict:
    """
    Very lightweight conversion of a raw JD string into the same entity-dict
    shape that the NER extractor produces for resumes, so we can embed both
    with embed_components() and run cosine similarity per component.
    """
    return {
        "skills": [job_description],
        "experience": [job_description],
        "projects": [job_description],
        "certifications": [job_description],
    }


# ---------------------------------------------------------------------------
# Main route
# ---------------------------------------------------------------------------

@router.post("/analyze", response_model=AnalysisResultResponse)
async def analyze_resume(req: AnalyzeRequest):
    resume_id = req.resume_id
    job_description = req.job_description

    print(f"Analyzing resume_id={resume_id}")

    # ------------------------------------------------------------------
    # Step 1: Fetch resume doc
    # ------------------------------------------------------------------
    try:
        oid = ObjectId(resume_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid resume_id format.")

    resume_doc = resume_collection.find_one({"_id": oid})
    if not resume_doc:
        raise HTTPException(status_code=404, detail="Resume not found.")

    s3_key = resume_doc.get("s3_key")
    if not s3_key:
        raise HTTPException(status_code=422, detail="S3 key not found for this resume.")

    # ------------------------------------------------------------------
    # Step 2: Download PDF from S3
    # ------------------------------------------------------------------
    file_bytes = download_file(s3_key)

    # ------------------------------------------------------------------
    # Step 3: Extract raw text
    # ------------------------------------------------------------------
    raw_text = extract_text(file_bytes)

    # ------------------------------------------------------------------
    # Step 4a: Clean text (two versions — one for NER, one for embeddings)
    # ------------------------------------------------------------------
    ner_text = clean_text_for_ner(raw_text)
    embedding_text = clean_text(raw_text)

    # ------------------------------------------------------------------
    # Step 4b: NER — extract structured entities from resume
    # ------------------------------------------------------------------
    entities = extract_entities(resume_text=ner_text, job_description=job_description)
    resume_skills: list = entities.get("skills", [])

    # ------------------------------------------------------------------
    # Step 4c: Embeddings + weighted cosine similarity match score
    # ------------------------------------------------------------------
    resume_components = embed_components(entities)

    if job_description.strip():
        jd_entities = _jd_to_entities(job_description)
        jd_components = embed_components(jd_entities)
        similarity_result = calculate_weighted_component_similarity(
            resume_components, jd_components, DEFAULT_WEIGHTS
        )
        match_score = round(similarity_result["weighted_average_score"])
        component_scores = similarity_result["individual_scores"]

        # Real JD-vs-resume skill overlap: run NER on the JD text itself
        # (same extractor, no new dependency) to get a comparable skill list.
        jd_entity_dict = extract_entities(resume_text=job_description, job_description="")
        jd_skills = jd_entity_dict.get("skills", [])
        jd_skills_lower = {s.lower() for s in jd_skills}
        resume_skills_lower = {s.lower() for s in resume_skills}
        matched_skills = [s for s in resume_skills if s.lower() in jd_skills_lower]
        missing_skills_raw = [s for s in jd_skills if s.lower() not in resume_skills_lower]
    else:
        # No JD provided → fall back to overall text embedding magnitude
        emb = get_embedding(embedding_text)
        match_score = 0
        component_scores = {}
        matched_skills = resume_skills
        missing_skills_raw = []

    # ------------------------------------------------------------------
    # Step 5: Build result document
    # ------------------------------------------------------------------
    # NOTE: predicted role and salary are no longer computed here. They're
    # derived from the user's real, ranked job matches instead — see
    # app/services/market_insights.py, served by GET /api/dashboard/summary.
    match_score = max(0, min(100, match_score))

    if match_score >= 70:
        match_status = "good"
        match_label = "Strong match"
    elif match_score >= 45:
        match_status = "warn"
        match_label = "Moderate match"
    else:
        match_status = "crit"
        match_label = "Needs improvement"

    result_doc = {
        "resume_id": resume_id,
        "user_id": str(resume_doc.get("user_id", "")),
        "filename": resume_doc.get("filename", ""),
        "analyzed_at": datetime.utcnow(),
        "match": {
            "score": match_score,
            "status": match_status,
            "status_label": match_label,
            "note": (
                f"Your resume aligns with <strong>{match_score}%</strong> of the job "
                f"requirements based on skill embeddings."
            ),
            "component_scores": component_scores,
        },
        "entities": entities,
        "matched_skills": matched_skills[:12],          # cap for display
        "missing_skills": [
            # TODO(you): "medium" is hardcoded until market_trends_data.py
            # can score real demand from job_postings_collection.
            {"name": s, "demand": "medium"} for s in missing_skills_raw[:8]
        ],
    }

    # ------------------------------------------------------------------
    # Step 7: Save to analysis_collection
    # ------------------------------------------------------------------
    insert_result = analysis_collection.insert_one(result_doc)
    result_doc["_id"] = str(insert_result.inserted_id)

    log_activity(
        user_id=result_doc["user_id"],
        type="analysis",
        message=f"Resume analyzed — {match_score}% match",
        icon="file",
        meta={"analysis_id": result_doc["_id"], "match_score": match_score},
    )

    # ------------------------------------------------------------------
    # Step 8: Return structured result to client
    # ------------------------------------------------------------------
    return result_doc
