"""
pipeline/db/local.py
────────────────────
SQLAlchemy engine and session factory for the local Postgres (full dataset).

Usage:
    from pipeline.db.local import LocalSession

    with LocalSession() as session:
        session.add(...)
        session.commit()

Run directly to create/upgrade all tables:
    python -m pipeline.db.local              # create + upgrade (idempotent)
    python -m pipeline.db.local --reset      # drop_all + create (DESTRUCTIVE)
"""
from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pipeline.config import settings
from pipeline.db.models import Base
from pipeline.db.schema import ensure_schema, list_tables, missing_tables

log = logging.getLogger(__name__)

engine = create_engine(
    settings.local_db_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

LocalSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def create_all_tables() -> None:
    """Create missing tables and apply column upgrades (idempotent)."""
    ensure_schema(engine)


def drop_all_tables() -> None:
    """Drop ALL tables — DESTRUCTIVE. Only use in dev/reset."""
    log.warning("Dropping all tables on local Postgres!")
    Base.metadata.drop_all(bind=engine)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
    parser = argparse.ArgumentParser(description="Local Postgres schema manager")
    parser.add_argument("--reset", action="store_true", help="Drop all tables then recreate (DESTRUCTIVE)")
    args = parser.parse_args(argv)

    if args.reset:
        drop_all_tables()
    create_all_tables()

    tables = list_tables(engine)
    print(f"✓ Local Postgres has {len(tables)} tables: {', '.join(tables)}")
    missing = missing_tables(engine)
    if missing:
        print(f"✗ Missing tables: {sorted(missing)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
