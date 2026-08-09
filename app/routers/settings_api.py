"""
app/routers/settings_api.py — Settings CRUD API.

Handles: GET/PATCH /api/settings, PATCH /api/settings/digest-hour

Real DB reads/writes against user_settings_collection, no external
credentials involved.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.security import get_current_user
from app.services.settings_data import get_settings_context, update_notification_settings, update_digest_hour

router = APIRouter()


class NotificationSettingsUpdate(BaseModel):
    email_alerts_enabled: bool


class DigestHourUpdate(BaseModel):
    digest_hour: int  # UTC hour 0-23


@router.get("/settings")
async def read_settings(user_id: str = Depends(get_current_user)):
    return get_settings_context(user_id)


@router.patch("/settings")
async def patch_settings(
    body: NotificationSettingsUpdate, user_id: str = Depends(get_current_user)
):
    return update_notification_settings(user_id, body.email_alerts_enabled)


@router.patch("/settings/digest-hour")
async def patch_digest_hour(
    body: DigestHourUpdate, user_id: str = Depends(get_current_user)
):
    """
    Save the user's preferred UTC hour for the daily job digest email.
    Accepts 0-23. Example: 9 = 9 AM UTC = 2:30 PM IST.
    """
    try:
        return update_digest_hour(user_id, body.digest_hour)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

