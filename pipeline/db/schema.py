"""
pipeline/db/schema.py
─────────────────────
Idempotent schema management shared by the local and Neon databases.

`create_all()` only creates *missing tables*; it never adds columns to
tables that already exist.  UPGRADES below fills that gap with plain
`IF NOT EXISTS` DDL so every environment converges on the current models
without a separate migration tool.  Every statement must be safe to run
on every pipeline start.
"""
from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

from pipeline.db.models import Base
from pipeline.symbols import CRYPTO, INDICES

log = logging.getLogger(__name__)

EXPECTED_TABLES = frozenset(Base.metadata.tables)

_TICKER_FIXES = sorted(
    {(c, f"{c}-USD") for c in CRYPTO}
    | {(alias, canon) for alias, (canon, _) in INDICES.items() if alias != canon and "'" not in alias}
)

UPGRADES: list[str] = [
    # 2026-09 — original URL, extraction retry counter, report provenance
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS url TEXT",
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS extraction_attempts INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE reports ADD COLUMN IF NOT EXISTS provider TEXT",
    # Data fix — earlier price loads stored NaN rows from yfinance gaps
    "DELETE FROM prices_daily WHERE close = 'NaN' OR open = 'NaN'",
    # 2026-09 — defaults were declared as the string 'now()', which Postgres froze
    # into a constant at CREATE TABLE time. Make them real now() defaults.
    "ALTER TABLE articles ALTER COLUMN first_seen_at SET DEFAULT now()",
    "ALTER TABLE extractions ALTER COLUMN created_at SET DEFAULT now()",
    "ALTER TABLE reports ALTER COLUMN created_at SET DEFAULT now()",
    "ALTER TABLE story_clusters ALTER COLUMN created_at SET DEFAULT now()",
    # 2026-09 — India market, LLM sector fallback, report top picks
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'global'",
    "CREATE INDEX IF NOT EXISTS ix_articles_market ON articles (market)",
    "ALTER TABLE extractions ADD COLUMN IF NOT EXISTS sector TEXT",
    "ALTER TABLE reports ADD COLUMN IF NOT EXISTS top_picks JSONB",
    # Data fix — LLM tickers written as news writes them ("BTC", "NIFTY 50") → canonical symbols
    # (see pipeline/symbols.py), so quotes and price history resolve. Touches only matching rows.
    *(
        f"UPDATE extractions SET tickers = array_replace(tickers, '{alias}', '{canon}') WHERE '{alias}' = ANY(tickers)"
        for alias, canon in _TICKER_FIXES
    ),
]


def ensure_schema(engine: Engine) -> None:
    """Create missing tables and apply additive upgrades (idempotent)."""
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        for stmt in UPGRADES:
            conn.execute(text(stmt))
    log.debug("Schema up to date on %s", engine.url.render_as_string(hide_password=True))


def list_tables(engine: Engine) -> list[str]:
    """Return the public table names that currently exist."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")
        )
        return [row[0] for row in rows]


def missing_tables(engine: Engine) -> set[str]:
    return set(EXPECTED_TABLES) - set(list_tables(engine))
