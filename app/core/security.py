"""
app/core/security.py — JWT Authentication (Optional but Recommended)

Handles user authentication using JSON Web Tokens (JWT).

What is JWT?
- A signed token the server gives to a client after login
- The client sends it with every request in the Authorization header
- The server verifies the signature to confirm the user's identity
- No session stored on server — stateless auth

Key functions:

1. create_access_token(data: dict) → token string
   - Takes user info (e.g. {"sub": user_id})
   - Signs it with SECRET_KEY + expiry time
   - Returns a JWT string the client stores (in localStorage or cookie)

2. verify_token(token: str) → user_id
   - Decodes and validates the JWT
   - Raises 401 Unauthorized if invalid or expired

3. get_current_user (FastAPI Dependency)
   - Used as: current_user = Depends(get_current_user)
   - Automatically extracts + validates token from request headers
   - Inject into any route that requires authentication

Dependencies:
- python-jose for JWT encoding/decoding
- passlib for password hashing (bcrypt)
"""

import logging
import bcrypt
from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.config import settings

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def hash_password(password: str) -> str:
    # Hash a plaintext password before storing in DB
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(plain: str, hashed: str) -> bool:
    # Compare plaintext against hashed (during login)
    try:
        pwd_bytes = plain.encode('utf-8')
        hashed_bytes = hashed.encode('utf-8')
        return bcrypt.checkpw(pwd_bytes, hashed_bytes)
    except Exception as exc:
        # Never log `plain`/`hashed` — just the fact that verification errored.
        logger.warning("Password verification error: %s", exc)
        return False

def create_access_token(data: dict) -> str:
    # Sign and encode user data into a JWT
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt

def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    # FastAPI dependency — validates JWT on protected routes
    # Returns the user_id embedded in the token
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return user_id
    except JWTError as exc:
        # Never log the raw token — just that validation failed and why.
        logger.warning("JWT validation failed: %s", exc)
        raise credentials_exception
