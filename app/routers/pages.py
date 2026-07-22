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


@router.get("/history")
async def history_page(request: Request):
    return templates.TemplateResponse(
        "history.html", {"request": request, "active_nav": "history"}
    )


@router.get("/activity")
async def activity_page(request: Request):
    return templates.TemplateResponse(
        "activity.html", {"request": request, "active_nav": "activity"}
    )


@router.get("/market-trends")
async def market_trends_page(request: Request):
    from app.services.market_trends_data import get_market_trends_context
    context = get_market_trends_context(user_id="demo")
    context.update({"request": request, "active_nav": "market-trends"})
    return templates.TemplateResponse("market_trends.html", context)


@router.get("/settings")
async def settings_page(request: Request):
    from app.config import settings as app_settings
    context = {
        "request": request,
        "active_nav": "settings",
        "integrations": {
            "job_api_configured": bool(app_settings.job_api_key),
            "email_configured": app_settings.email_enabled,
        },
    }
    return templates.TemplateResponse("settings.html", context)


@router.get("/agent")
async def agent_page(request: Request):
    return templates.TemplateResponse(
        "agent.html", {"request": request, "active_nav": "agent"}
    )