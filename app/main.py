import sys
from pathlib import Path

# Add project root to sys.path to allow running the app directly
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import registration, login
from app.step1_api import upload_resume_1

app = FastAPI(title="TalentMap API", version="1.0.0")

# -- Middleware --
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -- Register Routers --
app.include_router(registration.router)
app.include_router(login.router)
app.include_router(upload_resume_1.router, prefix="/api")

from fastapi.responses import RedirectResponse

@app.get("/")
async def root():
    return RedirectResponse(url="/login")