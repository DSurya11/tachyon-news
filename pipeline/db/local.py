"""
pipeline/db/local.py
────────────────────
SQLAlchemy engine and session factory for the local Docker Postgres.

Usage:
    from pipeline.db.local import LocalSession, engine

    with LocalSession() as session:
        session.add(...)
        session.commit()

Run directly to create/verify all tables:
    python pipeline/db/local.py              # create_all
    python pipeline/db/local.py --reset      # drop_all + create_all (DESTRUCTIVE)
"""
from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from pipeline.config import settings
from pipeline.db.models import Base

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Engine (synchronous — most pipeline stages are fine with sync Postgres)
# ---------------------------------------------------------------------------
engine = create_engine(
    settings.local_db_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,       # drop stale connections
    echo=False,               # set True temporarily to debug SQL
)

# Session factory — use as context manager
LocalSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def create_all_tables() -> None:
    """Create all tables that don't yet exist (idempotent)."""
    log.info("Creating tables on local Postgres...")
    Base.metadata.create_all(bind=engine)
    log.info("Done.")


def drop_all_tables() -> None:
    """Drop ALL tables — DESTRUCTIVE. Only use in dev/reset."""
    log.warning("Dropping all tables on local Postgres (--reset flag set)!")
    Base.metadata.drop_all(bind=engine)
    log.warning("All tables dropped.")


def verify_tables() -> list[str]:
    """Return the list of table names that currently exist."""
    with engine.connect() as conn:
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

    parser = argparse.ArgumentParser(description="Local Postgres migration runner")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop all tables then recreate (DESTRUCTIVE — dev only!)",
    )
    args = parser.parse_args()

    if args.reset:
        drop_all_tables()

    create_all_tables()

    tables = verify_tables()
    print(f"\n✓ Tables in local Postgres ({len(tables)} total):")
    for t in tables:
        print(f"   {t}")

    if len(tables) < 9:
        print("\n✗ Expected at least 9 tables! Check your models.", file=sys.stderr)
        sys.exit(1)

    print("\n✓ Milestone 0 verify: all tables exist in local Postgres.")
