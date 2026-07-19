"""app/routers/pages.py — authenticated app pages (dashboard, new analysis).

Auth on these routes is enforced client-side (static/js/auth-guard.js
redirects to /login when localStorage has no token) rather than via a
FastAPI dependency: the token lives in localStorage from the JSON login
flow, not in a cookie, so it never reaches the server on a plain page
navigation.
"""

from fastapi import APIRouter, Request

from app.core.templates import templates
from app.services.dashboard_data import get_sample_dashboard_context

router = APIRouter()


@router.get("/dashboard")
async def dashboard_page(request: Request):
    context = get_sample_dashboard_context(user_id="demo")
    context.update({"request": request, "active_nav": "dashboard"})
    return templates.TemplateResponse("dashboard.html", context)


@router.get("/new-analysis")
async def new_analysis_page(request: Request):
    return templates.TemplateResponse(
        "upload.html", {"request": request, "active_nav": "upload"}
    )