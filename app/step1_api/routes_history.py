"""
app/step1_api/routes_history.py — User History Route

Handles: GET /api/history

Flow:
1. Identify the caller via the JWT (Depends(get_current_user)) — never a
   trusted user_id from the URL, matching upload_resume_1.py's pattern.
2. Query analysis_collection for all analyses tied to that user.
3. Sort by analyzed_at descending (most recent first), paginate.
4. Return a list of past analysis results.
"""

from fastapi import APIRouter, Depends

from app.core.db import analysis_collection
from app.core.security import get_current_user

router = APIRouter()


@router.get("/history")
async def get_history(user_id: str = Depends(get_current_user), skip: int = 0, limit: int = 20):
    docs = list(
        analysis_collection.find({"user_id": user_id})
        .sort("analyzed_at", -1)
        .skip(skip)
        .limit(limit)
    )
    for d in docs:
        d["_id"] = str(d["_id"])
    return {"user_id": user_id, "count": len(docs), "results": docs}
