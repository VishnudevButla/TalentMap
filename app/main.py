"""
app/main.py — FastAPI App Entrypoint

This is the root of the FastAPI application.
- Creates the FastAPI() instance
- Registers all API routers (resume, analyze, history)
- Can add global middleware here (CORS, logging, auth)
- Run with: uvicorn app.main:app --reload
"""

# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
# from app.api import routes_resume, routes_analyze, routes_history

# app = FastAPI(title="TalentMap API", version="1.0.0")

# -- Middleware --
# app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)

# -- Register Routers --
# app.include_router(routes_resume.router, prefix="/api")
# app.include_router(routes_analyze.router, prefix="/api")
# app.include_router(routes_history.router, prefix="/api")