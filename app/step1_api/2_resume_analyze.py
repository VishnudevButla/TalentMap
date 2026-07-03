"""
app/api/routes_analyze.py — Resume Analysis Route

Handles: POST /api/analyze

Flow:
1. Client sends { resume_id } in request body
2. Fetch the resume document from MongoDB to get the s3_key
3. Download the PDF bytes from S3 using the presigned URL (or direct download)
4. Run NLP pipeline:
   a. pdf_parser.py     → extract raw text from PDF
   b. preprocess.py     → clean and normalize the text
   c. ner_extractor.py  → extract skills, education, experience using spaCy
   d. embeddings.py     → generate vector embedding for similarity scoring
5. Run ML inference:
   a. predict.py        → predict job role (classifier) + salary range (regressor)
6. Save analysis results to MongoDB (analysis_collection)
7. Return structured results to client

Dependencies:
- app.core.db            → resume_collection, analysis_collection
- app.core.s3_utils      → get_presigned_url() or direct download
- app.nlp.pdf_parser     → extract_text()
- app.nlp.preprocess     → clean_text()
- app.nlp.ner_extractor  → extract_entities()
- app.nlp.embeddings     → get_embedding(), compute_similarity()
- app.ml.predict         → predict_role(), predict_salary()
- app.schemas.result_schema → AnalysisResponse
"""

from app.core.s3_utils import download_file
from bson import ObjectId
from fastapi import APIRouter
from app.core.db import resume_collection, analysis_collection
# pyrefly: ignore [missing-import]
from app.nlp.pdf_parser import extract_text
# pyrefly: ignore [missing-import]
from app.nlp.preprocess import clean_text
# pyrefly: ignore [missing-import]
from app.nlp.ner_extraction import extract_entities
# pyrefly: ignore [missing-import]
from app.nlp.embeddings import get_embedding
# pyrefly: ignore [missing-import]
from app.ml.predict import predict_role, predict_salary

router = APIRouter()

@router.post("/analyze")
async def analyze_resume(resume_id: str):

    print(f"Analyzing resume with ID: {resume_id}")

    # Step 1: Fetch resume doc from MongoDB
    resume_doc = resume_collection.find_one({"_id": ObjectId(resume_id)})

    if not resume_doc:
        return {"error": "Resume not found"}

    s3_key = resume_doc.get("s3_key")
    if not s3_key:
        return {"error": "S3 key not found for this resume"}

    # Step 2: Download PDF from S3
    file_bytes = download_file(s3_key)
    # Step 3: Extract raw text from PDF
    raw_text = extract_text(file_bytes)
    # Step 4: Clean and preprocess text
    cleaned_text = clean_text(raw_text)
    # Step 5: Run NER to extract structured entities
    entities = extract_entities(cleaned_text)
    # Step 6: Generate embedding vector
    embedding = get_embedding(cleaned_text)
    print("embedding shape:", embedding.shape)
    print("EMBEDDINGS GENERATED!!")
    # Step 7: Predict role + salary
    # Step 8: Save results to MongoDB
    # Step 9: Return results
    pass
