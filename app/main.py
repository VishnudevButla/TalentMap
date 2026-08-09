import sys
import logging
from contextlib import asynccontextmanager
from pathlib import Path

# Add project root to sys.path to allow running the app directly
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Logging must be configured before any app.* module is imported below —
# app.core.db connects to MongoDB at import time, and that import is
# triggered transitively by the router imports that follow.
from app.core.logger import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.routers import registration, login, pages, activity_api, settings_api, dashboard_api, market_trends_api
from app.step1_api import upload_resume_1, resume_analyze_2, routes_history
from app.step4_agent import routes_agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    # The AI Job Agent scheduler no longer starts here — it runs in a
    # separate process (worker.py) so scans keep happening regardless of
    # whether this API process is up. Run `python worker.py` alongside
    # this app; see README.md's "Running the app" section.
    logger.info("TalentMap API starting up")
    yield
    logger.info("TalentMap API shutting down")


app = FastAPI(title="TalentMap API", version="1.0.0", lifespan=lifespan)
main = app

# -- Middleware --
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -- Static assets (CSS/JS shared by every template) --
class _RevalidateStaticFiles(StaticFiles):
    """
    StaticFiles with no explicit Cache-Control header lets browsers use
    heuristic caching (RFC 7234) — they can keep serving an old cached
    copy of a .js/.css file for hours after it changed on disk, with no
    request even reaching the server, since there's nothing forcing a
    freshness check. That silently reintroduces pre-edit behavior (stale
    UI logic, "stuck" states) that looks like a real bug but is really
    just a stale browser cache. no-cache forces a conditional GET
    (If-None-Match/If-Modified-Since) on every load — the server still
    replies 304 and skips re-sending unchanged bytes, so this doesn't
    disable caching's bandwidth benefit, it just guarantees every load
    reflects what's actually on disk right now.
    """
    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


static_dir = project_root / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", _RevalidateStaticFiles(directory=str(static_dir)), name="static")

# -- Register Routers --
app.include_router(registration.router)
app.include_router(login.router)
app.include_router(pages.router)
app.include_router(upload_resume_1.router, prefix="/api")
app.include_router(resume_analyze_2.router, prefix="/api")
app.include_router(routes_history.router, prefix="/api")
app.include_router(activity_api.router, prefix="/api")
app.include_router(settings_api.router, prefix="/api")
app.include_router(dashboard_api.router, prefix="/api")
app.include_router(market_trends_api.router, prefix="/api")
app.include_router(routes_agent.router, prefix="/api")

from fastapi.responses import RedirectResponse

@app.get("/")
async def root():
    return RedirectResponse(url="/login")
