"""
app/schemas/result_schema.py — Pydantic Validation Models for Resume Analysis Results

This module contains data models for the NLP and ML analysis pipeline outcomes.
Ensures FastAPI endpoints return consistent, validated structures.

Flow:
1. Define NER results structure (skills, education, experience lists).
2. Define ML classification outputs (role labels, prediction confidence).
3. Define ML regression outputs (estimated salary band min/max).
4. Define Match scoring outcomes (similarity score against job descriptions).
5. Define the unified AnalysisResultResponse schema.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

class NERResult(BaseModel):
    """
    Extracted entities from the resume.
    """
    # skills: List[str] - List of identified skills (e.g. ['python', 'scikit-learn'])
    # education: List[str] - List of identified academic paths/degrees
    # experience: List[str] - List of previous job titles / companies
    # projects: List[str] - List of projects described in the resume
    # certifications: List[str] - List of professional certifications
    pass

class MLResult(BaseModel):
    """
    Predictive outcomes from classifier and regressor models.
    """
    # predicted_role: str - Target classification role (e.g. "Backend Engineer")
    # role_confidence: float - Probability score of classification accuracy
    # estimated_salary_min: float - Lower bounds of estimated salary band
    # estimated_salary_max: float - Upper bounds of estimated salary band
    pass

class MatchResult(BaseModel):
    """
    Comparison scoring result against a target job description.
    """
    # job_description_id: Optional[str] - Target job description compared
    # component_scores: Dict[str, float] - Cosine similarity score for individual components (skills, projects, certifications, experience)
    # weighted_match_score_percentage: float - Weighted average cosine similarity percentage (0-100)
    pass

class AnalysisResultResponse(BaseModel):
    """
    Complete consolidated result of NLP/ML processing.
    """
    # resume_id: str - Target resume identifier
    # user_id: str - Target user identifier
    # text_extracted: str - Preview or raw text representation
    # entities: NERResult - Output of Named Entity Recognition stage
    # predictions: MLResult - Output of role/salary ML models
    # job_matches: List[MatchResult] - Matching lists against stored JDs
    # analyzed_at: datetime - Timestamp of analysis completion
    pass
