"""
app/schemas/result_schema.py — Pydantic Validation Models for Resume Analysis Results

This module contains data models for the NLP analysis pipeline outcomes.
Ensures FastAPI endpoints return consistent, validated structures.

Flow:
1. Define NER results structure (skills, education, experience lists).
2. Define Match scoring outcomes (similarity score against job descriptions).
3. Define the unified AnalysisResultResponse schema.

PredictedRoleInfo/SalaryBand are defined here too, but are no longer part
of AnalysisResultResponse — they describe the shape returned by
app/services/market_insights.py (derived from real job matches), consumed
by GET /api/dashboard/summary.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime


class NERResult(BaseModel):
    """
    Extracted entities from the resume (shape produced by
    app/step2_nlp/ner_extraction_3.extract_entities).
    """
    skills: List[str] = Field(default_factory=list)
    education: List[str] = Field(default_factory=list)
    experience: List[str] = Field(default_factory=list)
    projects: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    # Present only when Gemini extraction failed — kept so the client can
    # tell "no skills found" apart from "extraction errored".
    error: Optional[str] = Field(default=None, alias="_error")

    model_config = {"populate_by_name": True}


class MissingSkill(BaseModel):
    name: str
    demand: str = "medium"  # TODO(you): replace with real demand once
                             # app/services/market_trends_data.py aggregates
                             # skill frequency from real job_postings_collection.


class MatchSummary(BaseModel):
    score: int
    status: str  # "good" | "warn" | "crit"
    status_label: str
    note: str
    component_scores: Dict[str, float] = Field(default_factory=dict)


class PredictedRoleInfo(BaseModel):
    """Derived from the user's top-ranked job matches — see market_insights.py."""
    title: str
    confidence: float
    alternates: List[str] = Field(default_factory=list)


class SalaryBand(BaseModel):
    """Derived from the user's top-ranked job matches — see market_insights.py."""
    median: int
    axis_min: int
    axis_max: int
    market_min: int
    market_max: int


class AnalysisResultResponse(BaseModel):
    """
    Complete consolidated result of NLP processing, matching the document
    saved to analysis_collection by app/step1_api/resume_analyze_2.py.
    """
    id: Optional[str] = Field(default=None, alias="_id")
    resume_id: str
    user_id: str
    filename: str
    analyzed_at: datetime
    match: MatchSummary
    entities: NERResult
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[MissingSkill] = Field(default_factory=list)

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}
