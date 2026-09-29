"""
backend/db.py
─────────────
Database session for the public API.

DSN priority: API_DB_URL → RENDER_DB_URL → NEON_DB_URL → LOCAL_DB_URL.
In production point API_DB_URL at a *read-only* Neon role, and AUTH_DB_URL at a
role that may write only the users / user_sessions tables.
"""
from __future__ import annotations

import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from pipeline.config import settings


def resolve_db_url() -> str:
    return settings.api_db_url or os.getenv("RENDER_DB_URL", "") or settings.neon_db_url or settings.local_db_url


db_url = resolve_db_url()
connect_args = {"sslmode": "require"} if "neon.tech" in db_url and "sslmode=" not in db_url else {}

engine = create_engine(
    db_url,
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True,
    pool_recycle=300,  # Neon closes idle connections
    connect_args=connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Accounts need write access, which the production API role (read-only Neon) lacks.
# AUTH_DB_URL points at a role that can write users/user_sessions; locally it is the same DB.
auth_db_url = settings.auth_db_url or db_url
auth_engine = engine if auth_db_url == db_url else create_engine(
    auth_db_url,
    pool_size=3,
    max_overflow=3,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args={"sslmode": "require"} if "neon.tech" in auth_db_url and "sslmode=" not in auth_db_url else {},
)
AuthSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=auth_engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_auth_db() -> Iterator[Session]:
    db = AuthSessionLocal()
    try:
        yield db
    finally:
        db.close()
