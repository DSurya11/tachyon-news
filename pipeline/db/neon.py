"""
pipeline/db/neon.py
───────────────────
SQLAlchemy engine and session factory for the Neon cloud database.

This module is used ONLY for the laptop → Neon sync (write direction).
The FastAPI backend on Render connects to Neon directly via its own
environment variables, using a read-only role.

Usage:
    from pipeline.db.neon import NeonSession

    with NeonSession() as session:
        session.add(...)
        session.commit()

Run directly to create/verify all tables on Neon:
    python pipeline/db/neon.py

IMPORTANT: NEON_DB_URL must be set in .env before running.
"""
from __future__ import annotations

import logging
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from pipeline.config import settings
from pipeline.db.models import Base

log = logging.getLogger(__name__)


def _build_neon_engine():
    """
    Build the Neon engine, but only if NEON_DB_URL is configured.
    Returns None gracefully if the URL is empty (so imports don't crash
    when Neon isn't set up yet during early development).
    """
    url = settings.neon_db_url
    if not url:
        log.warning(
            "NEON_DB_URL is not set — Neon engine will be unavailable. "
            "Set it in .env when you have a Neon project."
        )
        return None

    return create_engine(
        url,
        pool_size=2,        # Neon free tier has limited connections
        max_overflow=3,
        pool_pre_ping=True,
        echo=False,
        connect_args={
            # Neon uses SSL by default
            "sslmode": "require",
        },
    )


neon_engine = _build_neon_engine()

# Session factory — will be None if NEON_DB_URL is not set
NeonSession = sessionmaker(bind=neon_engine, autocommit=False, autoflush=False) if neon_engine else None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def create_all_tables() -> None:
    """Create all tables on Neon that don't yet exist (idempotent)."""
    if neon_engine is None:
        log.error("Cannot run Neon migrations: NEON_DB_URL is not configured.")
        sys.exit(1)
    log.info("Creating tables on Neon...")
    Base.metadata.create_all(bind=neon_engine)
    log.info("Done.")


def verify_tables() -> list[str]:
    """Return the list of table names that currently exist on Neon."""
    if neon_engine is None:
        return []
    with neon_engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' ORDER BY tablename"
            )
        )
        return [row[0] for row in result]


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    if not settings.neon_db_url:
        print("✗ NEON_DB_URL is not set in .env — cannot migrate Neon.", file=sys.stderr)
        print("  Set NEON_DB_URL and rerun: python pipeline/db/neon.py")
        sys.exit(1)

    create_all_tables()

    tables = verify_tables()
    print(f"\n✓ Tables in Neon ({len(tables)} total):")
    for t in tables:
        print(f"   {t}")

    if len(tables) < 9:
        print("\n✗ Expected at least 9 tables! Check your models.", file=sys.stderr)
        sys.exit(1)

    print("\n✓ Neon migration verified.")
