"""
pipeline/db/neon.py
───────────────────
SQLAlchemy engine and session factory for the Neon cloud database.

Used only for the laptop → Neon sync (write direction).  `neon_engine` and
`NeonSession` are None when NEON_DB_URL is not configured, so importing this
module never fails during local-only development.

Run directly to create/upgrade all tables on Neon:
    python -m pipeline.db.neon
"""
from __future__ import annotations

import logging
import sys

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from pipeline.config import settings
from pipeline.db.schema import ensure_schema, list_tables, missing_tables

log = logging.getLogger(__name__)


def _build_neon_engine() -> Engine | None:
    url = settings.neon_db_url
    if not url:
        return None
    connect_args = {} if "sslmode=" in url else {"sslmode": "require"}
    return create_engine(
        url,
        pool_size=2,          # Neon free tier has limited connections
        max_overflow=3,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


neon_engine = _build_neon_engine()
NeonSession = sessionmaker(bind=neon_engine, autocommit=False, autoflush=False) if neon_engine else None


def create_all_tables() -> None:
    """Create missing tables on Neon and apply column upgrades (idempotent)."""
    if neon_engine is None:
        raise RuntimeError("NEON_DB_URL is not configured")
    ensure_schema(neon_engine)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
    if neon_engine is None:
        print("⚠ NEON_DB_URL is not set — skipping Neon migration.")
        return 0
    create_all_tables()
    tables = list_tables(neon_engine)
    print(f"✓ Neon has {len(tables)} tables: {', '.join(tables)}")
    missing = missing_tables(neon_engine)
    if missing:
        print(f"✗ Missing tables: {sorted(missing)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
