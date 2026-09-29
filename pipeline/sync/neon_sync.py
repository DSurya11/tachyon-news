"""
pipeline/sync/neon_sync.py
──────────────────────────
Upserts the public-safe subset of the local database into Neon.

Incremental by default: only rows touched within NEON_SYNC_LOOKBACK_DAYS
are re-sent (the old version re-uploaded every table in full every hour).
Private columns never leave the laptop:
  articles.body, articles.title_hash, extractions.evidence, extractions.key_facts

CLI:
    python -m pipeline.sync.neon_sync          # incremental
    python -m pipeline.sync.neon_sync --full   # everything
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql import Select

from pipeline.config import settings
from pipeline.db import neon
from pipeline.db.local import LocalSession
from pipeline.db.models import Article, ArticleTicker, Extraction, PriceDaily, Report, ScrapeRun, SymbolCheck, Ticker
from pipeline.db.schema import ensure_schema

log = logging.getLogger(__name__)

PRIVATE_COLUMNS = {
    Article: {"body", "title_hash"},
    Extraction: {"evidence", "key_facts"},
}
PRICE_WINDOW_DAYS = 60


def _columns(model) -> list:
    excluded = PRIVATE_COLUMNS.get(model, set())
    return [c for c in model.__table__.columns if c.name not in excluded]


def _upsert(neon_session, model, rows: list[dict]) -> None:
    pk = [c.name for c in model.__table__.primary_key.columns]
    for i in range(0, len(rows), settings.neon_sync_chunk_size):
        stmt = insert(model).values(rows[i : i + settings.neon_sync_chunk_size])
        updates = {c.name: stmt.excluded[c.name] for c in _columns(model) if c.name not in pk}
        stmt = (
            stmt.on_conflict_do_update(index_elements=pk, set_=updates)
            if updates
            else stmt.on_conflict_do_nothing(index_elements=pk)
        )
        neon_session.execute(stmt)


def _sync(local_session, neon_session, model, query: Select) -> int:
    cols = _columns(model)
    rows = [dict(zip([c.name for c in cols], r, strict=True)) for r in local_session.execute(query.with_only_columns(*cols))]
    if rows:
        _upsert(neon_session, model, rows)
    log.info("Neon sync: %-15s %d rows", model.__tablename__, len(rows))
    return len(rows)


def _queries(full: bool) -> list[tuple[type, Select]]:
    cutoff = datetime.now(UTC) - timedelta(days=settings.neon_sync_lookback_days)
    recent_articles = or_(Article.last_seen_at >= cutoff, Article.first_seen_at >= cutoff)

    def maybe(query: Select, *conds) -> Select:
        return query if full else query.where(*conds)

    return [
        (Ticker, maybe(select(Ticker), Ticker.last_seen_at >= cutoff)),
        (Article, maybe(select(Article), recent_articles)),
        (
            ArticleTicker,
            select(ArticleTicker)
            if full
            else select(ArticleTicker).join(Article, Article.id == ArticleTicker.article_id).where(recent_articles),
        ),
        (
            Extraction,
            select(Extraction)
            if full
            else select(Extraction)
            .join(Article, Article.id == Extraction.article_id)
            .where(or_(Extraction.created_at >= cutoff, recent_articles)),
        ),
        (PriceDaily, maybe(select(PriceDaily), PriceDaily.date >= datetime.now(UTC).date() - timedelta(days=PRICE_WINDOW_DAYS))),
        (ScrapeRun, maybe(select(ScrapeRun), ScrapeRun.started_at >= cutoff)),
        (Report, maybe(select(Report), Report.created_at >= cutoff)),
        (SymbolCheck, maybe(select(SymbolCheck), SymbolCheck.checked_at >= cutoff)),
    ]


def sync_to_neon(full: bool = False) -> dict[str, int] | None:
    """Sync local → Neon. Returns row counts, or None when Neon is not configured."""
    if neon.neon_engine is None or neon.NeonSession is None:
        log.info("NEON_DB_URL not configured — skipping Neon sync.")
        return None

    ensure_schema(neon.neon_engine)
    counts: dict[str, int] = {}
    with LocalSession() as local_session, neon.NeonSession() as neon_session:
        for model, query in _queries(full):
            counts[model.__tablename__] = _sync(local_session, neon_session, model, query)
        neon_session.commit()
    log.info("Neon sync complete (%s): %d rows", "full" if full else "incremental", sum(counts.values()))
    return counts


def main(argv: list[str] | None = None) -> int:
    from pipeline.logging_setup import setup_logging

    setup_logging(None)
    parser = argparse.ArgumentParser(description="Sync the public dataset to Neon")
    parser.add_argument("--full", action="store_true", help="Sync every row, not just recent ones")
    args = parser.parse_args(argv)
    sync_to_neon(full=args.full)
    return 0


if __name__ == "__main__":
    sys.exit(main())
