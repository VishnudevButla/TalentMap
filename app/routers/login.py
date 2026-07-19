import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request, status

# Ensure sys.path resolver is added to run/test directly
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.core.db import user_collection
from app.core.templates import templates
from app.schemas.resume_schema import UserLogin
from app.core.security import verify_password, create_access_token

router = APIRouter()

@router.get("/login")
async def get_login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request})

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
