"""
pipeline/prices/yahoo.py
────────────────────────
Daily OHLCV candles via yfinance (Finnhub's free tier does not serve /candle).

Only tickers mentioned in the last PRICES_ACTIVE_DAYS are refreshed — both the ones
Finviz attached to a story and the ones the LLM extracted (Indian stocks, crypto,
indices and many US names only come from the LLM), since the dashboard shows both.  Tickers
with little history get a longer backfill (for 30-day sparklines); the rest
only fetch the last few sessions.  Rows with missing prices are skipped.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import pandas as pd
import yfinance as yf
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from pipeline.config import settings
from pipeline.db.local import LocalSession
from pipeline.db.models import Article, ArticleTicker, Extraction, PriceDaily, SymbolCheck
from pipeline.market_time import ET
from pipeline.symbols import fx_pair, is_unlisted, native_currency, yahoo_symbol

log = logging.getLogger(__name__)

BACKFILL_DAYS = 45       # ≈ 30 trading sessions
REFRESH_DAYS = 7
MIN_HISTORY_ROWS = 20
DOWNLOAD_CHUNK = 100
FALLBACK_TICKERS = ["SPY", "QQQ", "AAPL", "NVDA"]
# Rates the dashboard converts with (currency per 1 USD, stored like prices under
# Yahoo's pair symbol, e.g. "USDINR=X"). INR is always kept: it's a display currency.
ALWAYS_FX = ("USDINR=X",)
# Benchmarks the story outcomes are measured against (pipeline/prices/outcomes.py): always kept current.
BENCHMARKS = ("SPX", "NIFTY")
# A symbol is "invalid" after this many failed checks (one Yahoo hiccup must not hide a real stock),
# and invalid symbols are retried after RECHECK_DAYS.
INVALID_AFTER_FAILURES = 2
RECHECK_DAYS = 7


def _active_tickers(session) -> tuple[list[str], list[str]]:
    """Return (needs_backfill, needs_refresh) symbol lists."""
    since = datetime.now(UTC) - timedelta(days=settings.prices_active_days)
    finviz = session.execute(
        select(ArticleTicker.ticker)
        .join(Article, Article.id == ArticleTicker.article_id)
        .where(Article.last_seen_at >= since)
        .distinct()
    ).scalars()
    llm = session.execute(
        select(func.unnest(Extraction.tickers))
        .join(Article, Article.id == Extraction.article_id)
        .where(Article.last_seen_at >= since)
        .distinct()
    ).scalars()
    active = ({t for t in (*finviz, *llm) if t and not is_unlisted(t)} or set(FALLBACK_TICKERS)) | set(BENCHMARKS)
    recheck_before = datetime.now(UTC) - timedelta(days=RECHECK_DAYS)
    active -= set(session.execute(
        select(SymbolCheck.symbol).where(SymbolCheck.status == "invalid", SymbolCheck.checked_at >= recheck_before)
    ).scalars())

    history = dict(
        session.execute(
            select(PriceDaily.ticker, func.count())
            .where(PriceDaily.ticker.in_(active))
            .group_by(PriceDaily.ticker)
        ).all()
    )
    # Daily FX for every currency in play, so charts convert each day at that day's rate.
    active |= {p for t in active if (c := native_currency(t)) and (p := fx_pair(c))} | set(ALWAYS_FX)
    history |= dict(
        session.execute(
            select(PriceDaily.ticker, func.count()).where(PriceDaily.ticker.in_(active)).group_by(PriceDaily.ticker)
        ).all()
    )
    backfill = sorted(t for t in active if history.get(t, 0) < MIN_HISTORY_ROWS)
    refresh = sorted(t for t in active if history.get(t, 0) >= MIN_HISTORY_ROWS)
    return backfill, refresh


def _frame_rows(symbol: str, df: pd.DataFrame) -> list[dict]:
    rows = []
    for ts, row in df.iterrows():
        values = [row.get(c) for c in ("Open", "High", "Low", "Close")]
        if any(v is None or pd.isna(v) for v in values):
            continue
        volume = row.get("Volume")
        rows.append(
            {
                "ticker": symbol,
                "date": ts.date(),
                "open": float(values[0]),
                "high": float(values[1]),
                "low": float(values[2]),
                "close": float(values[3]),
                "volume": 0 if volume is None or pd.isna(volume) else int(volume),
            }
        )
    return rows


def _download(symbols: list[str], days: int) -> list[dict]:
    if not symbols:
        return []
    today = datetime.now(ET).date()  # market-local date
    start = today - timedelta(days=days)
    end = today + timedelta(days=1)  # yfinance's end is exclusive
    rows: list[dict] = []
    for i in range(0, len(symbols), DOWNLOAD_CHUNK):
        chunk = symbols[i : i + DOWNLOAD_CHUNK]
        by_yahoo = {yahoo_symbol(s): s for s in chunk}
        data = yf.download(
            list(by_yahoo),
            start=start.isoformat(),
            end=end.isoformat(),
            group_by="ticker",
            auto_adjust=False,
            progress=False,
            threads=True,
        )
        if data is None or data.empty:
            continue
        for ysym, sym in by_yahoo.items():
            if isinstance(data.columns, pd.MultiIndex):
                if ysym not in data.columns.get_level_values(0):
                    continue
                frame = data[ysym]
            else:
                frame = data
            rows.extend(_frame_rows(sym, frame))
    return rows


def _upsert(session, rows: list[dict]) -> None:
    for i in range(0, len(rows), 1000):
        stmt = insert(PriceDaily).values(rows[i : i + 1000])
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker", "date"],
            set_={c: stmt.excluded[c] for c in ("open", "high", "low", "close", "volume")},
        )
        session.execute(stmt)


def _record_checks(session, asked: list[str], got: set[str]) -> int:
    """Mark symbols Yahoo answered as valid; count failures for the rest. Returns newly invalid."""
    now = datetime.now(UTC)
    prior = {c.symbol: c for c in session.execute(select(SymbolCheck).where(SymbolCheck.symbol.in_(asked))).scalars()}
    newly_invalid = 0
    for sym in asked:
        if sym.endswith("=X"):
            continue  # FX rates are ours, not ticker claims
        check = prior.get(sym) or SymbolCheck(symbol=sym, fail_count=0)
        if sym in got:
            check.status, check.fail_count = "valid", 0
        else:
            check.fail_count = (check.fail_count or 0) + 1
            was_invalid = check.status == "invalid"
            check.status = "invalid" if check.fail_count >= INVALID_AFTER_FAILURES else "pending"
            newly_invalid += check.status == "invalid" and not was_invalid
        check.checked_at = now
        session.add(check)
    return newly_invalid


def update_prices() -> dict:
    with LocalSession() as session:
        backfill, refresh = _active_tickers(session)
        log.info("Prices: %d tickers to backfill, %d to refresh", len(backfill), len(refresh))
        rows = _download(backfill, BACKFILL_DAYS) + _download(refresh, REFRESH_DAYS)
        _upsert(session, rows)
        if rows:  # a run where Yahoo returned nothing at all is an outage, not proof of bad symbols
            invalid = _record_checks(session, backfill, {r["ticker"] for r in rows})
            if invalid:
                log.info("Prices: %d symbols have no market data and are now hidden", invalid)
        session.commit()
    symbols_with_data = len({r["ticker"] for r in rows})
    log.info("Prices: upserted %d rows for %d tickers", len(rows), symbols_with_data)
    if (backfill or refresh) and not rows:
        raise RuntimeError("yfinance returned no price data (rate-limited or offline?)")
    return {"rows": len(rows), "tickers": symbols_with_data}


if __name__ == "__main__":
    from pipeline.logging_setup import setup_logging

    setup_logging(None)
    update_prices()
