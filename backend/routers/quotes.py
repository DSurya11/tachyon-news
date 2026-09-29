"""
Quotes: live price from Finnhub (cached 5 min), falling back to the last
daily close stored by the pipeline (marked "stale": true) when Finnhub is
not configured, rate-limited or does not know the symbol.

Every quote and chart says what its numbers are in: `currency` (ISO code, or
null for index points). `?currency=USD|INR` converts at the stored daily rate
(charts: each day at that day's rate); when a value can't be converted it is
returned in its native currency, never guessed.
"""
from __future__ import annotations

import asyncio
import bisect
import logging
import re
import time
from datetime import UTC, date, datetime, timedelta
from datetime import time as dtime

import httpx
from cachetools import TTLCache
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import desc, select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from backend import fx, history
from backend.db import get_db
from pipeline.config import settings
from pipeline.db.models import PriceDaily
from pipeline.market_time import ET
from pipeline.symbols import MINOR_UNITS, is_us_listed, native_currency, yahoo_symbol

log = logging.getLogger(__name__)

router = APIRouter(tags=["quotes"])

FINNHUB_QUOTE_URL = "https://finnhub.io/api/v1/quote"
MAX_BATCH = 50
CURRENCY_PARAM = Query("native", pattern="^(native|USD|INR)$", description="native (the listing's own), USD or INR")
# US symbols, or longer Indian symbols with an NSE/BSE suffix (same rule as extraction).
SYMBOL_RE = re.compile(r"^(?:[A-Z][A-Z0-9]{0,5}(?:[.\-][A-Z0-9]{1,3})?|[A-Z][A-Z0-9&\-]{0,14}\.(?:NS|BO))$")

_quote_cache: TTLCache = TTLCache(maxsize=2000, ttl=300)
_miss_cache: TTLCache = TTLCache(maxsize=2000, ttl=60)  # don't hammer Finnhub for bad symbols
_finnhub_sem = asyncio.Semaphore(10)
FINNHUB_COOLDOWN_S = 60
_finnhub_paused_until = 0.0  # monotonic time; set when Finnhub rate-limits us


def _normalize_symbol(raw: str) -> str:
    sym = raw.strip().upper()
    if not SYMBOL_RE.match(sym):
        raise HTTPException(status_code=422, detail=f"Invalid symbol: {raw!r}")
    return sym


async def _finnhub_quote(client: httpx.AsyncClient, symbol: str) -> dict | None:
    global _finnhub_paused_until
    if not settings.finnhub_api_key or symbol in _miss_cache or time.monotonic() < _finnhub_paused_until:
        return None
    if not is_us_listed(symbol):  # Finnhub's free tier: US equities only (not .NS, crypto or indices)
        return None
    try:
        async with _finnhub_sem:
            resp = await client.get(FINNHUB_QUOTE_URL, params={"symbol": symbol, "token": settings.finnhub_api_key})
        if resp.status_code == 429:
            # Free tier is 60 calls/min: stop calling for a while and serve last closes instead.
            if time.monotonic() >= _finnhub_paused_until:
                log.warning("Finnhub rate limit hit — using daily closes for %ds", FINNHUB_COOLDOWN_S)
            _finnhub_paused_until = time.monotonic() + FINNHUB_COOLDOWN_S
            return None
        resp.raise_for_status()
        raw = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("Finnhub quote failed for %s: %s", symbol, exc)
        _miss_cache[symbol] = True
        return None
    if not raw or not raw.get("c"):  # Finnhub answers unknown symbols with zeros
        _miss_cache[symbol] = True
        return None
    return {
        "symbol": symbol,
        "price": raw.get("c"),
        "change": raw.get("d") or 0.0,
        "pct_change": raw.get("dp") or 0.0,
        "t": raw.get("t", 0),
        "stale": False,
        "source": "finnhub",
    }


def _db_quote(db: Session, symbol: str) -> dict | None:
    rows = db.execute(
        select(PriceDaily.date, PriceDaily.close).where(PriceDaily.ticker == symbol).order_by(desc(PriceDaily.date)).limit(2)
    ).all()
    if not rows or rows[0].close is None:
        return None
    close = float(rows[0].close)
    prev = float(rows[1].close) if len(rows) > 1 and rows[1].close else None
    change = close - prev if prev else 0.0
    return {
        "symbol": symbol,
        "price": close,
        "change": round(change, 4),
        "pct_change": round(100 * change / prev, 4) if prev else 0.0,
        "as_of": rows[0].date.isoformat(),
        "stale": True,
        "source": "daily_close",
    }


async def _quote(request: Request, db: Session, symbol: str) -> dict | None:
    if symbol in _quote_cache:
        return _quote_cache[symbol]
    quote = await _finnhub_quote(request.app.state.http, symbol)
    if quote is None:
        quote = await run_in_threadpool(_db_quote, db, symbol)
    if quote is not None:
        _quote_cache[symbol] = quote
    return quote


def _in_currency(db: Session, quote: dict, target: str) -> dict:
    """A copy of a native quote, labelled with its currency and converted to `target` when possible."""
    out = dict(quote)
    native = native_currency(out["symbol"])
    out["currency"] = native
    out["native_currency"] = native
    if native is None:
        out["unit"] = "pts"  # index level or unknown instrument: never converted
        return out
    if target == "native" or target == native:
        return out
    conv = fx.rate(db, native, target)
    if conv is None:
        out["fx_unavailable"] = True  # shown in its own currency rather than a guessed one
        return out
    mult, as_of = conv
    out.update(
        currency=target,
        price=round(out["price"] * mult, 6),
        change=round(out["change"] * mult, 6),  # % change stays the listing's own move
        fx_rate=round(mult, 8),
        fx_as_of=as_of.isoformat() if as_of else None,
    )
    return out


@router.get("/quote/{symbol}")
async def get_quote(symbol: str, request: Request, currency: str = CURRENCY_PARAM, db: Session = Depends(get_db)):
    """Live price and % change (or the last daily close, flagged stale)."""
    sym = _normalize_symbol(symbol)
    quote = await _quote(request, db, sym)
    if quote is None:
        raise HTTPException(status_code=404, detail=f"No quote available for {sym}")
    return await run_in_threadpool(_in_currency, db, quote, currency)


@router.get("/quotes")
async def get_batch_quotes(
    request: Request,
    symbols: str = Query(..., description="Comma-separated, max 50"),
    currency: str = CURRENCY_PARAM,
    db: Session = Depends(get_db),
):
    """Batch quotes. Unknown or malformed symbols come back as {symbol, error}; they never fail the batch."""
    raw = list(dict.fromkeys(s.strip().upper() for s in symbols.split(",") if s.strip()))
    if len(raw) > MAX_BATCH:
        raise HTTPException(status_code=400, detail=f"Max {MAX_BATCH} symbols allowed")
    syms = [s for s in raw if SYMBOL_RE.match(s)]
    invalid = [{"symbol": s, "error": "Invalid symbol"} for s in raw if not SYMBOL_RE.match(s)]
    # The DB fallback shares one session, so resolve sequentially after the concurrent Finnhub calls.
    live = await asyncio.gather(*(_finnhub_quote(request.app.state.http, s) for s in syms if s not in _quote_cache))
    for q in live:
        if q:
            _quote_cache[q["symbol"]] = q
    results = []
    for sym in syms:
        quote = await _quote(request, db, sym)
        results.append(await run_in_threadpool(_in_currency, db, quote, currency) if quote else {"symbol": sym, "error": "No quote available"})
    return {"data": results + invalid}


@router.get("/candles/{symbol}")
def get_candles(
    symbol: str,
    days: int = Query(30, ge=1, le=365),
    currency: str = CURRENCY_PARAM,
    db: Session = Depends(get_db),
):
    """Daily closes (oldest first). Converted closes use each day's own FX rate."""
    sym = _normalize_symbol(symbol)
    rows = db.execute(
        select(PriceDaily.date, PriceDaily.close).where(PriceDaily.ticker == sym).order_by(desc(PriceDaily.date)).limit(days)
    ).all()
    rows = [r for r in reversed(rows) if r.close is not None]
    native = native_currency(sym)
    out_ccy = native
    points = [(r.date, float(r.close)) for r in rows]
    if native and currency not in ("native", native):
        converted = []
        for day, close in points:
            conv = fx.rate(db, native, currency, on=day)
            if conv is None:
                break
            converted.append((day, close * conv[0]))
        if len(converted) == len(points):  # all-or-nothing: never mix currencies in one chart
            points, out_ccy = converted, currency
    return {
        "symbol": sym,
        "currency": out_ccy,
        "unit": None if native else "pts",
        "dates": [d.isoformat() for d, _ in points],
        "candles": [round(c, 6) for _, c in points],
    }


def _yahoo_rates(major: str, period: str, interval: str) -> tuple[list[date], list[float]] | None:
    """`major` per 1 USD over a chart's span, from Yahoo (the stored rates cover ~45 days)."""
    if major == "USD":
        return None
    pts = history.bars(f"USD{major}=X", period, interval, 6 * 3600)
    return ([t.date() for t, _ in pts], [c for _, c in pts]) if pts else None


def _convert(db: Session, points: list, native: str, target: str, span: str) -> list | None:
    """Each point at its own day's rate; None unless every point converts (never mix currencies)."""
    if span in history.INTRADAY or span == "1m":
        out = []
        for t, c in points:
            conv = fx.rate(db, native, target, on=t.date() if isinstance(t, datetime) else t)
            if conv is None:
                return None
            out.append((t, c * conv[0]))
        return out
    period, interval = history.SPANS[span][:2]
    (n_major, n_minor), (t_major, t_minor) = MINOR_UNITS.get(native, (native, 1)), MINOR_UNITS.get(target, (target, 1))
    src, dst = _yahoo_rates(n_major, period, interval), _yahoo_rates(t_major, period, interval)
    if (n_major != "USD" and not src) or (t_major != "USD" and not dst):
        return None

    def per_usd(series, day):
        if series is None:
            return 1.0
        i = bisect.bisect_right(series[0], day) - 1
        return series[1][i] if i >= 0 and (day - series[0][i]).days <= 10 else None

    out = []
    for t, c in points:
        day = t.date() if isinstance(t, datetime) else t
        a, b = per_usd(src, day), per_usd(dst, day)
        if a is None or b is None:
            return None
        out.append((t, c * (b / a) * (t_minor / n_minor)))
    return out


def _stored_closes(db: Session, sym: str, days: int) -> list:
    since = datetime.now(UTC).date() - timedelta(days=days)
    rows = db.execute(
        select(PriceDaily.date, PriceDaily.close)
        .where(PriceDaily.ticker == sym, PriceDaily.date >= since, PriceDaily.close.is_not(None))
        .order_by(PriceDaily.date)
    ).all()
    return [(r.date, float(r.close)) for r in rows]


MIN_DAY_BARS = 6  # half an hour of 5-minute bars
REGULAR_CLOSE = dtime(16, 0)


@router.get("/chart/{symbol}")
def get_chart(
    symbol: str,
    span: str = Query("1m", pattern="^(1d|5d|1m|3m|6m|1y|5y)$"),
    currency: str = CURRENCY_PARAM,
    db: Session = Depends(get_db),
):
    """
    Price history for one span of the stock panel: 5-minute bars for 1D (with the previous
    close as `base`), 15-minute for 5D, daily up to 1Y, weekly for 5Y. From Yahoo on demand;
    `source: "stored"` when that fails and the pipeline's daily closes are shown instead.
    """
    sym = _normalize_symbol(symbol)
    period, interval, fresh_s, days = history.SPANS[span]
    # 1D for US listings includes pre-market and after-hours trading, like most apps' 1D view.
    extended = span == "1d" and native_currency(sym) == "USD"
    points = history.bars(yahoo_symbol(sym), period, interval, fresh_s, prepost=extended)
    source, intraday, base = "yahoo", span in history.INTRADAY, None
    if points and span == "1d":
        sessions = sorted({t.date() for t, _ in points})
        # A day that has barely begun (one or two bars just after the open) shows the last full one.
        day = sessions[-1] if sum(t.date() == sessions[-1] for t, _ in points) >= MIN_DAY_BARS or len(sessions) == 1 else sessions[-2]
        # The change is measured from the previous regular-session close, not its after-hours trades.
        before = [c for t, c in points if t.date() < day and (not extended or t.astimezone(ET).time() < REGULAR_CLOSE)]
        base = before[-1] if before else None
        points = [(t, c) for t, c in points if t.date() == day]
    if not points:
        points, source, intraday = _stored_closes(db, sym, max(days, 7)), "stored", False
    native = native_currency(sym)
    out_ccy = native
    if native and currency not in ("native", native) and points:
        converted = _convert(db, points + ([(points[0][0], base)] if base else []), native, currency, span)
        if converted:
            if base:
                base = converted.pop()[1]
            points, out_ccy = converted, currency
    return {
        "symbol": sym,
        "span": span,
        "source": source,
        "intraday": intraday,
        "extended": extended and source == "yahoo",
        "currency": out_ccy,
        "unit": None if native else "pts",
        "base": round(base, 6) if base else (round(points[0][1], 6) if points else None),
        "dates": [t.isoformat() for t, _ in points],
        "candles": [round(c, 6) for _, c in points],
    }
