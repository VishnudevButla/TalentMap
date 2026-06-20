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
from app.schemas.resume_schema import UserLogin
from app.core.security import verify_password, create_access_token

router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates"

@router.get("/login", response_class=HTMLResponse)
async def get_login_page():
    login_html_path = TEMPLATES_DIR / "login.html"
    if not login_html_path.exists():
        raise HTTPException(status_code=404, detail="login.html not found")
    with open(login_html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)

@router.post("/api/login")
async def login_user(user_in: UserLogin):
    email = user_in.email.lower()
    
    user = user_collection.find_one({"email": email})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password."
        )
    
    if not verify_password(user_in.password, user.get("hashed_password", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password."
        )
    
    # Generate JWT
    access_token = create_access_token(data={"sub": str(user["_id"])})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(user["_id"]),
            "username": user["username"],
            "email": user["email"]
        }
    }
