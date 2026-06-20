import sys
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import HTMLResponse

# Ensure sys.path resolver is added to run/test directly
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.core.db import user_collection
from app.schemas.resume_schema import UserCreate, UserResponse
from app.core.security import hash_password

router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates"

@router.get("/register", response_class=HTMLResponse)
async def get_register_page():
    register_html_path = TEMPLATES_DIR / "register.html"
    if not register_html_path.exists():
        raise HTTPException(status_code=404, detail="register.html not found")
    with open(register_html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)

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
    return user_doc
