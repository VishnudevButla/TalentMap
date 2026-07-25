"""
app/routers/market_trends_api.py — Market Trends API

Handles: GET /api/market-trends

The page itself (templates/market_trends.html) is server-rendered with a
generic sample pre-hydration payload — same pattern as dashboard_api.py —
since auth lives in localStorage, not a cookie, and never reaches a plain
page navigation. This endpoint is what actually personalizes the page to
the logged-in user client-side.
"""

from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.services.market_trends_data import get_market_trends_context

router = APIRouter()


@router.get("/market-trends")
async def market_trends_summary(user_id: str = Depends(get_current_user)):
    return get_market_trends_context(user_id)
