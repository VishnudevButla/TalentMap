"""
app/schemas/resume_schema.py — Pydantic Validation Models for Resume Ingestion

This module contains data structure models using Pydantic's BaseModel
to validate API payloads for resume upload and metadata fields.

Flow:
1. Define request models (e.g. metadata or file attributes passed during upload).
2. Define response models (e.g. indicating upload success, returning generated resume ID).
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class ResumeUploadResponse(BaseModel):
    """
    Schema returned after successful resume file upload.
    """
    # resume_id: str - Unique identifier generated for the resume
    # s3_key: str - Location where file is saved in S3
    # user_id: str - Owner/uploader identifier
    # status: str - "SUCCESS" or "FAILED"
    # uploaded_at: datetime - Timestamp of ingestion
    pass

class ResumeMetadata(BaseModel):
    """
    Metadata representation of a candidate resume stored in DB.
    """
    # id: str - MongoDB primary key string representation
    # user_id: str - Owner of the resume
    # file_name: str - Original filename (e.g., Jane_Doe_Resume.pdf)
    # file_size_bytes: int - Size of the uploaded file
    # s3_key: str - Object storage index key
    # uploaded_at: datetime - Upload timestamp
    # status: str - Status of pipeline analysis (e.g. "uploaded", "processing", "analyzed", "error")
    pass
