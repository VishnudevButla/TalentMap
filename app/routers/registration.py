import sys
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, status

# Ensure sys.path resolver is added to run/test directly
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.core.db import user_collection
from app.core.templates import templates
from app.schemas.resume_schema import UserCreate, UserResponse
from app.core.security import hash_password
from app.step4_agent.state import ensure_agent_state

router = APIRouter()

@router.get("/register")
async def get_register_page(request: Request):
    return templates.TemplateResponse("auth/register.html", {"request": request})

@router.post("/api/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_in: UserCreate):
    email = user_in.email.lower()
    
    # Check if user already exists
    existing_user = user_collection.find_one({"email": email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists."
        )
    
    # Hash password and store
    hashed_password = hash_password(user_in.password)
    
    user_doc = {
        "username": user_in.username,
        "email": email,
        "hashed_password": hashed_password,
        "created_at": datetime.utcnow()
    }
    
    result = user_collection.insert_one(user_doc)

    # Assign the inserted string id
    user_doc["_id"] = str(result.inserted_id)

    # Seed a default AI Job Agent state so /agent and /api/agent/status work
    # immediately for a brand-new user — real DB write, no external creds.
    ensure_agent_state(user_doc["_id"])

    return user_doc
