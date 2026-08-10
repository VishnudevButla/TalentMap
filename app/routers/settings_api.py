"""
app/routers/settings_api.py — Settings CRUD API.

Handles: GET/PATCH /api/settings, PATCH /api/settings/digest-hour,
PATCH /api/settings/email-frequency, PATCH /api/settings/match-threshold

Real DB reads/writes against user_settings_collection, no external
credentials involved. Every field here is actually read by the live
worker (app/step4_agent/scheduler.py, matcher.py) — see settings_data.py.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.services.settings_data import (
    EMAIL_FREQUENCIES,
    get_settings_context,
    update_notification_settings,
    update_digest_hour,
    update_email_frequency,
    update_match_threshold,
)

router = APIRouter()


class NotificationSettingsUpdate(BaseModel):
    email_alerts_enabled: bool


class DigestHourUpdate(BaseModel):
    digest_hour: int  # UTC hour 0-23


class EmailFrequencyUpdate(BaseModel):
    email_frequency: str


class MatchThresholdUpdate(BaseModel):
    match_threshold: int = Field(ge=0, le=100)


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
    Accepts 0-23. Example: 9 = 9 AM UTC = 2:30 PM IST. Only actually
    matters when email_frequency is "daily" — see scheduler.py.
    """
    try:
        return update_digest_hour(user_id, body.digest_hour)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.patch("/settings/email-frequency")
async def patch_email_frequency(
    body: EmailFrequencyUpdate, user_id: str = Depends(get_current_user)
):
    """
    "immediate" | "daily" | "weekly" | "never" — the live worker
    (scheduler.py's run_scan_cycle + send_daily_digest) reads this
    directly, not just a display-only preference.
    """
    if body.email_frequency not in EMAIL_FREQUENCIES:
        raise HTTPException(
            status_code=422,
            detail=f"email_frequency must be one of {EMAIL_FREQUENCIES}",
        )
    try:
        return update_email_frequency(user_id, body.email_frequency)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.patch("/settings/match-threshold")
async def patch_match_threshold(
    body: MatchThresholdUpdate, user_id: str = Depends(get_current_user)
):
    """
    The score (0-100) at which a match is "worth telling you about" —
    read directly by matcher.py (activity log) and scheduler.py (digest
    eligibility), not just stored for display.
    """
    try:
        return update_match_threshold(user_id, body.match_threshold)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
