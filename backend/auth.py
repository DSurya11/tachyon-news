"""
backend/auth.py
───────────────
Accounts for the dashboard: password hashing, login sessions and the
`current_user` dependency that guards every data endpoint.

Sessions are opaque bearer tokens (random 256-bit). Only their SHA-256 is
stored, so a database leak does not leak usable sessions. Bearer tokens (not
cookies) because the dashboard and API live on different sites in production.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from cachetools import TTLCache
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.db import get_auth_db
from pipeline.config import settings
from pipeline.db.models import User, UserSession

# ---------------------------------------------------------------------------
# Passwords (scrypt, stdlib)
# ---------------------------------------------------------------------------

_SCRYPT_N, _SCRYPT_R, _SCRYPT_P, _DKLEN = 2**14, 8, 1, 64


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_DKLEN)
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        # Same cost as a real check, so response time doesn't reveal whether the account exists.
        hash_password(password)
        return False
    try:
        _, n, r, p, salt, digest = stored.split("$")
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CurrentUser:
    id: int
    email: str
    name: str | None


_session_cache: TTLCache = TTLCache(maxsize=10_000, ttl=60)  # token hash → (CurrentUser, expires_at)
_lock = threading.Lock()  # cachetools caches are not thread-safe; sync endpoints run in a pool


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    db.add(UserSession(token_hash=_token_hash(token), user_id=user.id, created_at=now,
                       expires_at=now + timedelta(days=settings.auth_session_days)))
    user.last_login_at = now
    # Opportunistic cleanup of this user's expired sessions.
    db.execute(delete(UserSession).where(UserSession.user_id == user.id, UserSession.expires_at < now))
    db.commit()
    return token


def revoke_session(db: Session, token: str) -> None:
    th = _token_hash(token)
    with _lock:
        _session_cache.pop(th, None)
    db.execute(delete(UserSession).where(UserSession.token_hash == th))
    db.commit()


def _bearer(request: Request) -> str | None:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token.strip() else None


def _unauthorized(detail: str = "Sign in to continue") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def bearer_token(request: Request) -> str:
    token = _bearer(request)
    if token is None:
        raise _unauthorized()
    return token


def current_user(token: str = Depends(bearer_token), db: Session = Depends(get_auth_db)) -> CurrentUser:
    """FastAPI dependency: the signed-in user, or 401."""
    th = _token_hash(token)
    with _lock:
        cached = _session_cache.get(th)
    now = datetime.now(UTC)
    if cached is None:
        row = db.execute(
            select(User.id, User.email, User.name, UserSession.expires_at)
            .join(UserSession, UserSession.user_id == User.id)
            .where(UserSession.token_hash == th)
        ).first()
        if row is None:
            raise _unauthorized("Your session has ended — sign in again")
        cached = (CurrentUser(row.id, row.email, row.name), row.expires_at)
        with _lock:
            _session_cache[th] = cached
    user, expires_at = cached
    if expires_at <= now:
        with _lock:
            _session_cache.pop(th, None)
        raise _unauthorized("Your session has expired — sign in again")
    return user


# ---------------------------------------------------------------------------
# Login throttling (in-process; enough for a single API instance)
# ---------------------------------------------------------------------------

_attempts: TTLCache = TTLCache(maxsize=50_000, ttl=15 * 60)
MAX_PER_IP = 30
MAX_PER_EMAIL = 10


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def check_rate(request: Request, email: str) -> None:
    for key, limit in ((f"ip:{client_ip(request)}", MAX_PER_IP), (f"email:{email}", MAX_PER_EMAIL)):
        with _lock:
            count = _attempts.get(key, 0)
        if count >= limit:
            raise HTTPException(status_code=429, detail="Too many attempts — try again in a few minutes")


def record_failure(request: Request, email: str) -> None:
    with _lock:
        for key in (f"ip:{client_ip(request)}", f"email:{email}"):
            _attempts[key] = _attempts.get(key, 0) + 1
    time.sleep(0.2)  # blunt online guessing a little further


def clear_failures(email: str) -> None:
    with _lock:
        _attempts.pop(f"email:{email}", None)
