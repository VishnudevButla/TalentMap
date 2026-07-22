import sys
from pathlib import Path

# Add project root to sys.path to allow running the app directly
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.routers import registration, login, pages, activity_api, settings_api, dashboard_api
from app.step1_api import upload_resume_1, resume_analyze_2, routes_history
from app.step4_agent import routes_agent

app = FastAPI(title="TalentMap API", version="1.0.0")
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
app.mount("/static", StaticFiles(directory=str(project_root / "static")), name="static")

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
app.include_router(routes_agent.router, prefix="/api")

from fastapi.responses import RedirectResponse

@app.get("/")
async def root():
    return RedirectResponse(url="/login")