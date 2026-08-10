"""
app/routers/oauth_google.py — "Continue with Google" sign-in/sign-up.

A plain server-redirect OAuth2 Authorization Code flow against Google,
implemented directly with `requests` (already a dependency) rather than
pulling in authlib/session middleware — this app's auth is already
stateless JWT-in-localStorage, so the OAuth handshake stays stateless too:
the anti-CSRF `state` param is a short-lived signed JWT (same secret/lib
as app.core.security), not server-side session storage.

Flow:
  GET  /api/auth/google/login    → redirect to Google's consent screen
  GET  /api/auth/google/callback → Google redirects back with ?code&state;
                                    exchange code, fetch profile, upsert
                                    the user, then redirect to a landing
                                    page with a one-time "handoff" token
                                    (NOT the real session token — see below)
  GET  /auth/google/complete     → landing page; its JS immediately POSTs
                                    the handoff token to /finalize
  POST /api/auth/google/finalize → redeems the handoff token and returns
                                    the real access_token + user, exactly
                                    like POST /api/login's response shape

The real bearer token is deliberately never put in a URL/redirect/browser
history — only a handoff token is, and that token is genuinely single-use:
it's a random opaque value whose only copy lives in oauth_handoff_collection
(app/core/db.py), and /finalize claims it with find_one_and_delete — an
atomic claim-and-burn, not just a short expiry. (An earlier version of this
file used a self-contained signed JWT for the handoff instead; that's
stateless-verifiable but replayable within its expiry window since nothing
tracks whether it's already been redeemed — caught by testing a replay
directly, not by inspection.)
"""

import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

import requests
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import settings
from app.core.db import user_collection, oauth_handoff_collection
from app.core.templates import templates
from app.core.security import create_access_token
from app.step4_agent.state import ensure_agent_state

logger = logging.getLogger(__name__)

router = APIRouter()

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

_STATE_PURPOSE = "google_oauth_state"


def _redirect_uri() -> str:
    return f"{settings.app_base_url}/api/auth/google/callback"


def _require_configured() -> None:
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google sign-in isn't configured yet.",
        )


def _sign(payload: dict) -> str:
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def _verify(token: str, purpose: str) -> dict:
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    if payload.get("purpose") != purpose:
        raise JWTError(f"expected purpose={purpose}")
    return payload


@router.get("/api/auth/google/login")
async def google_login():
    _require_configured()
    state = _sign({"purpose": _STATE_PURPOSE, "exp": datetime.utcnow() + timedelta(minutes=5)})
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")


@router.get("/api/auth/google/callback")
async def google_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    _require_configured()

    if error:
        logger.warning("Google OAuth denied or failed: %s", error)
        return RedirectResponse("/login?oauth_error=google_denied")

    if not code or not state:
        return RedirectResponse("/login?oauth_error=google_failed")

    try:
        _verify(state, _STATE_PURPOSE)
    except JWTError:
        logger.warning("Google OAuth callback: invalid or expired state")
        return RedirectResponse("/login?oauth_error=google_failed")

    try:
        token_res = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": _redirect_uri(),
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
        token_res.raise_for_status()
        google_access_token = token_res.json()["access_token"]

        userinfo_res = requests.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {google_access_token}"},
            timeout=10,
        )
        userinfo_res.raise_for_status()
        profile = userinfo_res.json()
    except (requests.RequestException, KeyError, ValueError) as exc:
        logger.error("Google OAuth token/userinfo exchange failed: %s", exc)
        return RedirectResponse("/login?oauth_error=google_failed")

    if not profile.get("email_verified"):
        logger.warning("Google OAuth: unverified email rejected")
        return RedirectResponse("/login?oauth_error=google_unverified")

    email = profile["email"].lower()
    user = user_collection.find_one({"email": email})

    if not user:
        user_doc = {
            "username": profile.get("name") or email.split("@")[0],
            "email": email,
            "hashed_password": None,
            "auth_provider": "google",
            "created_at": datetime.utcnow(),
        }
        result = user_collection.insert_one(user_doc)
        user_doc["_id"] = result.inserted_id
        ensure_agent_state(str(result.inserted_id))
        user = user_doc
        logger.info("New user registered via Google: user_id=%s", str(user["_id"]))
    else:
        logger.info("User logged in via Google: user_id=%s", str(user["_id"]))

    handoff = secrets.token_urlsafe(32)
    oauth_handoff_collection.insert_one({
        "_id": handoff,
        "user_id": str(user["_id"]),
        "created_at": datetime.utcnow(),
    })
    return RedirectResponse(f"/auth/google/complete?handoff={handoff}")


@router.get("/auth/google/complete")
async def google_complete_page(request: Request):
    return templates.TemplateResponse("auth/oauth_complete.html", {"request": request})


class HandoffIn(BaseModel):
    handoff: str


@router.post("/api/auth/google/finalize")
async def google_finalize(body: HandoffIn):
    # Atomic claim-and-burn — a replayed/reused token finds nothing the
    # second time, regardless of how quickly it's retried.
    doc = oauth_handoff_collection.find_one_and_delete({"_id": body.handoff})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign-in link expired. Please try again.",
        )

    user = user_collection.find_one({"_id": ObjectId(doc["user_id"])})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account no longer exists.")

    access_token = create_access_token(data={"sub": str(user["_id"])})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {"id": str(user["_id"]), "username": user["username"], "email": user["email"]},
    }
