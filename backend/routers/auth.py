"""
Accounts: email + password sign-up/sign-in, "Continue with Google", sign-out.

Every call returns a bearer token for `Authorization: Bearer <token>`.
Google sign-in is enabled by setting GOOGLE_CLIENT_ID (Google Identity Services).
"""
from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.auth import (
    CurrentUser,
    bearer_token,
    check_rate,
    clear_failures,
    create_session,
    current_user,
    hash_password,
    record_failure,
    revoke_session,
    verify_password,
)
from backend.db import get_auth_db
from pipeline.config import settings
from pipeline.db.models import User

log = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
GOOGLE_ISSUERS = ["accounts.google.com", "https://accounts.google.com"]
_google_keys = jwt.PyJWKClient("https://www.googleapis.com/oauth2/v3/certs", cache_keys=True, lifespan=6 * 3600)


class SignupIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)
    name: str | None = Field(default=None, max_length=80)


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


class GoogleIn(BaseModel):
    credential: str = Field(max_length=4096)


def _user_out(user: User) -> dict:
    return {"id": user.id, "email": user.email, "name": user.name,
            "has_password": user.password_hash is not None, "google": user.google_sub is not None}


def _session_out(db: Session, user: User) -> dict:
    return {"token": create_session(db, user), "user": _user_out(user)}


def _norm_email(raw: str) -> str:
    email = raw.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="Enter a valid email address")
    return email


def _find(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(func.lower(User.email) == email)).scalar_one_or_none()


@router.get("/config")
def auth_config() -> dict:
    """Public: which sign-in methods the dashboard should offer."""
    return {"google_client_id": settings.google_client_id or None, "password": True, "signup": True}


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(body: SignupIn, request: Request, db: Session = Depends(get_auth_db)) -> dict:
    email = _norm_email(body.email)
    check_rate(request, email)
    if len(body.password) < 8:
        raise HTTPException(status_code=422, detail="Use at least 8 characters for your password")
    existing = _find(db, email)
    if existing is not None:
        detail = ("This email signs in with Google — use Continue with Google"
                  if existing.password_hash is None else "An account with this email already exists — sign in instead")
        raise HTTPException(status_code=409, detail=detail)
    user = User(email=email, name=(body.name or "").strip() or None, password_hash=hash_password(body.password),
                created_at=datetime.now(UTC))
    db.add(user)
    try:
        db.flush()
    except IntegrityError:  # a concurrent sign-up with the same email
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists — sign in instead") from None
    return _session_out(db, user)


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_auth_db)) -> dict:
    email = body.email.strip().lower()
    check_rate(request, email)
    user = _find(db, email) if EMAIL_RE.match(email) else None
    if user is None or not verify_password(body.password, user.password_hash if user else None):
        record_failure(request, email)
        if user is not None and user.password_hash is None:
            raise HTTPException(status_code=401, detail="This account uses Google — use Continue with Google")
        raise HTTPException(status_code=401, detail="Wrong email or password")
    clear_failures(email)
    return _session_out(db, user)


def verify_google_credential(credential: str) -> dict:
    """Verify a Google Identity Services ID token; returns its claims."""
    if not settings.google_client_id:
        raise HTTPException(status_code=404, detail="Google sign-in is not enabled")
    try:
        key = _google_keys.get_signing_key_from_jwt(credential).key
        claims = jwt.decode(credential, key, algorithms=["RS256"], audience=settings.google_client_id,
                            issuer=GOOGLE_ISSUERS, options={"require": ["exp", "iat", "sub", "email"]})
    except jwt.PyJWTError as exc:
        log.info("Rejected Google credential: %s", exc)
        raise HTTPException(status_code=401, detail="Google sign-in failed — try again") from None
    if not claims.get("email_verified"):
        raise HTTPException(status_code=401, detail="Your Google email isn't verified")
    return claims


@router.post("/google")
def google(body: GoogleIn, db: Session = Depends(get_auth_db)) -> dict:
    claims = verify_google_credential(body.credential)
    sub, email = str(claims["sub"]), str(claims["email"]).lower()
    user = db.execute(select(User).where(User.google_sub == sub)).scalar_one_or_none()
    if user is None:
        # Google has verified this email, so linking it to an existing password account is safe.
        user = _find(db, email)
        if user is None:
            user = User(email=email, name=claims.get("name"), created_at=datetime.now(UTC))
            db.add(user)
        user.google_sub = sub
        user.name = user.name or claims.get("name")
        db.flush()
    return _session_out(db, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(token: str = Depends(bearer_token), db: Session = Depends(get_auth_db)) -> Response:
    revoke_session(db, token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me")
def me(user: CurrentUser = Depends(current_user), db: Session = Depends(get_auth_db)) -> dict:
    row = db.get(User, user.id)
    if row is None:
        raise HTTPException(status_code=401, detail="Your account no longer exists")
    return _user_out(row)
