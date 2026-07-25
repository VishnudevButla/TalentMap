"""
app/routers/activity_api.py — Activity Feed Route

Handles: GET /api/activity

Reads activity_log_collection entries written by other parts of the app
(resume analysis, the AI Job Agent scan cycle, settings changes) and
returns them newest-first for the Activity page and the dashboard's
Recent Activity preview.
"""

from typing import Optional

from fastapi import APIRouter, Depends

from app.core.db import activity_log_collection
from app.core.security import get_current_user

router = APIRouter()


@router.get("/activity")
async def get_activity(
    user_id: str = Depends(get_current_user),
    skip: int = 0,
    limit: int = 30,
    type: Optional[str] = None,
):
    query = {"user_id": user_id}
    if type:
        query["type"] = type
    docs = list(
        activity_log_collection.find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    for d in docs:
        d["_id"] = str(d["_id"])
    return {"user_id": user_id, "count": len(docs), "results": docs}
