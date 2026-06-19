"""
app/api/routes_resume.py — Resume Upload Route

Handles: POST /api/upload-resume

Flow:
1. Client sends a PDF file via multipart form upload
2. Read file bytes from the request
3. Call s3_utils.upload_file() to store the PDF in S3
4. Save metadata (filename, s3_key, timestamp, user_id) to MongoDB
5. Return the resume_id and s3_key to the client

Dependencies:
- app.core.s3_utils  → upload_file()
- app.core.db        → resume_collection
- app.schemas.resume_schema → ResumeUploadResponse
"""

# from fastapi import APIRouter, UploadFile, File
# from datetime import datetime
# from app.core.s3_utils import upload_file
# from app.core.db import resume_collection
# from app.schemas.resume_schema import ResumeUploadResponse

# router = APIRouter()

# @router.post("/upload-resume", response_model=ResumeUploadResponse)
# async def upload_resume(file: UploadFile = File(...)):
#     # Step 1: Read raw bytes from uploaded PDF
#     # Step 2: Upload to S3, get back the S3 key (path)
#     # Step 3: Build a MongoDB document with metadata
#     # Step 4: Insert into resume_collection
#     # Step 5: Return resume_id + s3_key
#     pass
