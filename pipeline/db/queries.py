"""
pipeline/db/queries.py
──────────────────────
Read helpers shared by the report builder and the public API.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from pipeline.db.models import ArticleTicker, SymbolCheck, Ticker
from pipeline.symbols import is_unlisted

MACRO_SECTOR = "Macro & Markets"
NON_SECTORS = frozenset({"", "Unknown", "Other"})


def article_tickers(
    session: Session, article_ids: Iterable[int], llm_tickers: dict[int, list[str] | None] | None = None
) -> dict[int, list[str]]:
    """Finviz-attached tickers per article, merged with LLM-confirmed tickers."""
    ids = list(article_ids)
    merged: dict[int, set[str]] = defaultdict(set)
    if ids:
        for article_id, symbol in session.execute(
            select(ArticleTicker.article_id, ArticleTicker.ticker).where(ArticleTicker.article_id.in_(ids))
        ):
            merged[article_id].add(symbol)
    for article_id, symbols in (llm_tickers or {}).items():
        merged[article_id].update(symbols or [])
    # Drop symbols the price stage couldn't find market data for (LLM inventions like NSE.NS).
    # Hidden from the first failed check; a real symbol that merely hit a Yahoo hiccup
    # reappears on its next successful check.
    invalid = invalid_symbols(session, {t for ts in merged.values() for t in ts})
    return {aid: sorted(merged[aid] - invalid) for aid in ids}


def invalid_symbols(session: Session, symbols: Iterable[str]) -> set[str]:
    symbols = set(symbols)
    if not symbols:
        return set()
    return {s for s in symbols if is_unlisted(s)} | set(session.execute(
        select(SymbolCheck.symbol).where(SymbolCheck.symbol.in_(symbols), SymbolCheck.status.in_(("invalid", "pending")))
    ).scalars())


def sector_lookup(session: Session, symbols: Iterable[str]) -> dict[str, str]:
    """symbol → GICS sector, for symbols with a real sector."""
    symbols = set(symbols)
    if not symbols:
        return {}
    rows = session.execute(select(Ticker.symbol, Ticker.sector).where(Ticker.symbol.in_(symbols)))
    return {sym: sector for sym, sector in rows if sector and sector not in NON_SECTORS}


def sectors_for(tickers: Iterable[str], sector_of: dict[str, str], fallback: str | None = None) -> list[str]:
    """
    Sectors an article belongs to. Ticker sectors win; `fallback` (the LLM's sector,
    used for tickers Finviz doesn't know, e.g. Indian stocks) comes next; else 'Macro & Markets'.
    """
    return sorted({sector_of[t] for t in tickers if t in sector_of}) or [fallback or MACRO_SECTOR]


def primary_sector(tickers: Iterable[str], sector_of: dict[str, str], fallback: str | None = None) -> str:
    """Single sector for an article: the most common among its tickers (first wins ties)."""
    counts: dict[str, int] = {}
    for t in tickers:
        if t in sector_of:
            counts[sector_of[t]] = counts.get(sector_of[t], 0) + 1
    return max(counts, key=counts.__getitem__) if counts else (fallback or MACRO_SECTOR)
