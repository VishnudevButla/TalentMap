"""
app/routers/settings_api.py — Settings CRUD API.

Handles: GET/PATCH /api/settings

Real DB reads/writes against user_settings_collection, no external
credentials involved. The AI Job Agent has no per-user settings anymore —
it's a fully global scan, see app/step4_agent/routes_agent.py's
GET /api/agent/status.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import get_current_user
from app.services.settings_data import get_settings_context, update_notification_settings

router = APIRouter()


class NotificationSettingsUpdate(BaseModel):
    email_alerts_enabled: bool


@router.get("/settings")
async def read_settings(user_id: str = Depends(get_current_user)):
    return get_settings_context(user_id)


@router.patch("/settings")
async def patch_settings(
    body: NotificationSettingsUpdate, user_id: str = Depends(get_current_user)
):
    return update_notification_settings(user_id, body.email_alerts_enabled)
