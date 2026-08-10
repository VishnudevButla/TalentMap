"""app/routers/pages.py — authenticated app pages (dashboard, new analysis).

Auth on these routes is enforced client-side (static/js/auth-guard.js
redirects to /login when localStorage has no token) rather than via a
FastAPI dependency: the token lives in localStorage from the JSON login
flow, not in a cookie, so it never reaches the server on a plain page
navigation.
"""

from fastapi import APIRouter, Request

from app.core.templates import templates

router = APIRouter()


@router.get("/dashboard")
async def dashboard_page(request: Request):
    # Fully client-hydrated (see static/js/dashboard.js) — same reason as
    # history.html/activity.html/market_trends.html: the JWT lives in
    # localStorage, not a cookie, so real per-user data can't be computed
    # at this point. No server-side sample context — every section renders
    # an honest loading/empty state until GET /api/dashboard/summary lands.
    return templates.TemplateResponse(
        "dashboard.html", {"request": request, "active_nav": "dashboard"}
    )


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
    # Fully client-hydrated (see static/js/market-trends.js) — same reason
    # as history.html/activity.html: the JWT lives in localStorage, not a
    # cookie, so real per-user data can't be computed at this point.
    return templates.TemplateResponse(
        "market_trends.html", {"request": request, "active_nav": "market-trends"}
    )


@router.get("/settings")
async def settings_page(request: Request):
    from app.config import settings as app_settings
    context = {
        "request": request,
        "active_nav": "settings",
        "integrations": {
            # Settings has no "job_api_key" field — the real fields are
            # provider-specific (Adzuna needs both an app ID and key).
            "job_api_configured": bool(app_settings.ADZUNA_APP_ID and app_settings.ADZUNA_APP_KEY),
            "email_configured": app_settings.email_enabled,
        },
    }
    return templates.TemplateResponse("settings.html", context)


@router.get("/agent")
async def agent_page(request: Request):
    return templates.TemplateResponse(
        "agent.html", {"request": request, "active_nav": "agent"}
    )


@router.get("/matches")
async def matches_page(request: Request):
    # Fully client-hydrated (see static/js/matches.js), fetching every real
    # match from GET /api/jobs/matches — the dashboard only ever shows the
    # top few; this page is the full, unabridged, filterable list.
    return templates.TemplateResponse(
        "matches.html", {"request": request, "active_nav": "matches"}
    )


@router.get("/matches/{job_id}")
async def match_detail_page(request: Request, job_id: str):
    # job_id isn't used server-side — the page is client-hydrated from
    # GET /api/jobs/matches/{job_id} (see static/js/job-detail.js), same
    # pattern as every other page in this app.
    return templates.TemplateResponse(
        "job_detail.html", {"request": request, "active_nav": "matches"}
    )