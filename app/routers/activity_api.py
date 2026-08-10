"""
app/routers/activity_api.py — Activity Feed Route

Handles: GET /api/activity, PATCH /api/activity/{id}/read,
DELETE /api/activity/{id}, DELETE /api/activity

Reads activity_log_collection entries written by other parts of the app
(resume analysis, the AI Job Agent scan cycle) and returns them
newest-first for the Activity page and the dashboard's Recent Activity
preview.

The only real per-user CRUD that makes sense here (per an explicit "don't
build CRUD for its own sake" instruction): mark-as-read (auto-triggered by
clicking through to the relevant page — see static/js/activity.js — not a
separate button nobody would click), delete one entry, and clear
everything. There's no "update the message" or "create manually" — those
aren't real actions a user would ever take on an activity log.
"""

from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

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
        # Entries logged before this field existed have no "read" key at
        # all — default to False (unread) rather than guessing.
        d.setdefault("read", False)
    return {"user_id": user_id, "count": len(docs), "results": docs}


@router.patch("/activity/{activity_id}/read")
async def mark_activity_read(activity_id: str, user_id: str = Depends(get_current_user)):
    try:
        oid = ObjectId(activity_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid activity_id format.")

    result = activity_log_collection.update_one(
        {"_id": oid, "user_id": user_id}, {"$set": {"read": True}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Activity entry not found.")
    return {"activity_id": activity_id, "read": True}


@router.delete("/activity/{activity_id}")
async def delete_activity(activity_id: str, user_id: str = Depends(get_current_user)):
    try:
        oid = ObjectId(activity_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid activity_id format.")

    result = activity_log_collection.delete_one({"_id": oid, "user_id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Activity entry not found.")
    return {"deleted": True, "activity_id": activity_id}


@router.delete("/activity")
async def clear_activity(user_id: str = Depends(get_current_user)):
    result = activity_log_collection.delete_many({"user_id": user_id})
    return {"deleted": True, "count": result.deleted_count}
