"""
backend/reaction.py
───────────────────
The priced-in meter for one story. Two parts, kept apart on purpose:

  1. What each of its stocks has done since the headline, beyond the market: the last
     intraday bar that ended before publication → the latest bar, minus the benchmark's
     move (S&P 500 or Nifty 50) over the same time. Fact, from Yahoo.
  2. What similar stories (same event type and sentiment) were followed by, from
     event_outcomes: the move beyond the market by day 0 and at +1d/+5d, and how often the
     first-day move kept going rather than faded. History, never a forecast — and nothing
     at all until there are enough samples over enough different days.

The verdict compares (1) with the typical move in (2).
"""
from __future__ import annotations

import statistics
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, time, timedelta

from cachetools import TTLCache
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend import history
from pipeline.db.models import EventOutcome
from pipeline.market_time import ET
from pipeline.prices.outcomes import BENCHMARK
from pipeline.symbols import native_currency, yahoo_symbol

MIN_SAMPLES = 20
MAX_TICKERS = 12  # every ticker a story names, within reason
MIN_DAYS = 5  # distinct day-0 sessions: one wild market day must not pass for a pattern
CONTINUE_MIN = 0.005  # first-day moves smaller than this neither "keep going" nor "fade"

_group_cache: TTLCache = TTLCache(maxsize=256, ttl=600)


def _bars_for_age(age: timedelta) -> tuple[str, str, int]:
    """(Yahoo range, bar size, bar minutes) fine enough to place the headline, long enough to reach it."""
    if age <= timedelta(days=4):
        return "5d", "5m", 5
    if age <= timedelta(days=25):
        return "1mo", "30m", 30
    return "2y", "1h", 60


# Funds that are the market, or aren't stocks at all (bonds, gold, oil, volatility): measuring these
# "beyond the S&P 500" says nothing, so they show their own move only. Indices are always in this group.
BROAD_ETFS = frozenset({
    "SPY", "VOO", "IVV", "VTI", "QQQ", "DIA", "IWM", "RSP", "NIFTYBEES",
    "TLT", "IEF", "SHY", "BND", "AGG", "LQD", "HYG", "TIP", "GLD", "IAU", "SLV", "USO", "UNG", "UUP", "VXX", "UVXY",
})
# Live benchmark per listing currency: SPY rather than the S&P 500 index, because it trades before
# the open and after the close too, so it can be compared with a stock's pre-market move.
LIVE_BENCH = {"USD": "SPY", "INR": "NIFTY"}


def _is_index(symbol: str) -> bool:
    return native_currency(symbol) is None


def _session(t: datetime) -> str:
    """US session a bar falls in: 'pre' (4:00–9:30 ET), 'regular', or 'post' (16:00–20:00)."""
    et = t.astimezone(ET).time()
    return "pre" if et < time(9, 30) else "post" if et >= time(16, 0) else "regular"


def move_since(symbol: str, published_at: datetime) -> dict | None:
    """Price at the headline (last bar that ended before it) and now, from intraday bars.
    US listings include pre-market and after-hours trading, so a 3 AM story moves before the open."""
    age = datetime.now(UTC) - published_at
    period, interval, minutes = _bars_for_age(age)
    extended = native_currency(symbol) == "USD" and interval != "1h"
    bars = history.bars(yahoo_symbol(symbol), period, interval, 120, prepost=extended)
    before = [(t, c) for t, c in bars if t + timedelta(minutes=minutes) <= published_at]
    if not before or len(bars) < 2:
        return None
    (t0, p0), (t1, p1) = before[-1], bars[-1]
    traded = t1 > t0  # after the close, nothing has traded since the headline yet
    return {"t0": t0 + timedelta(minutes=minutes), "t0_price": round(p0, 4), "price": round(p1, 4),
            "price_at": t1 + timedelta(minutes=minutes), "traded": traded,
            "session": _session(t1) if extended else "regular",
            "move_pct": round((p1 / p0 - 1) * 100, 2) if traded else None}


def _pct(x) -> float | None:
    return None if x is None else round(float(x) * 100, 2)


def group_history(db: Session, event_type: str | None, sentiment: str | None) -> dict:
    key = (event_type, sentiment)
    if key in _group_cache:
        return _group_cache[key]
    rows = db.execute(
        select(EventOutcome.day0_date, EventOutcome.ret_day0 - func.coalesce(EventOutcome.bench_day0, 0),
               EventOutcome.ret_1d - EventOutcome.bench_1d, EventOutcome.ret_5d - EventOutcome.bench_5d)
        .where(EventOutcome.event_type == event_type, EventOutcome.sentiment == sentiment)
    ).all()
    done = {h: [r for r in rows if r[col] is not None] for h, col in (("1d", 2), ("5d", 3))}
    progress = {h: {"n": len(v), "days": len({r[0] for r in v})} for h, v in done.items()}
    out: dict = {"event_type": event_type, "sentiment": sentiment, "needed": MIN_SAMPLES, "needed_days": MIN_DAYS,
                 "progress": progress, "horizon": None}
    ready = next((h for h in ("5d", "1d") if progress[h]["n"] >= MIN_SAMPLES and progress[h]["days"] >= MIN_DAYS), None)
    if ready:
        col = 3 if ready == "5d" else 2
        later = sorted(float(r[col]) for r in done[ready])
        q = statistics.quantiles(later, n=4)
        moved = [(float(r[1]), float(r[col])) for r in done[ready] if abs(float(r[1])) >= CONTINUE_MIN]
        kept = sum(1 for a0, ah in moved if (ah - a0) * a0 > 0)
        out.update(horizon=ready, n=len(later), p25=_pct(q[0]), median=_pct(statistics.median(later)), p75=_pct(q[2]),
                   day0_median=_pct(statistics.median(float(r[1]) for r in done[ready])),
                   kept_going=round(kept / len(moved) * 100) if moved else None, moved_n=len(moved))
    _group_cache[key] = out
    return out


def verdict(excess_pct: float | None, hist: dict) -> str | None:
    """How much of the usual move has already happened. Wording describes history, not what to do."""
    if excess_pct is None or not hist.get("horizon"):
        return None
    usual = hist["median"]
    if abs(usual) < 0.5:
        return "usually_small"
    if excess_pct * usual < 0:
        return "against"
    share = excess_pct / usual
    return "mostly" if share >= 0.75 else "partly" if share >= 0.25 else "little"


def reaction(db: Session, article_id: int, published_at: datetime | None, tickers: list[str],
             event_type: str | None, sentiment: str | None) -> dict:
    hist = group_history(db, event_type, sentiment) if event_type else None
    approximate = bool(published_at and published_at.astimezone(ET).time() == datetime.min.time())
    # Company stocks first, then broad funds, then raw indices (they only trade in regular hours).
    ranked = sorted(tickers, key=lambda t: 2 if _is_index(t) else 1 if t in BROAD_ETFS else 0)
    out = []
    chosen = ranked[:MAX_TICKERS]
    # Every symbol's bars (and each benchmark's) fetched together: a story naming ten tickers
    # costs about one Yahoo round trip, not ten.
    symbols = list(dict.fromkeys([*chosen, *(LIVE_BENCH[c] for t in chosen if (c := native_currency(t)) in LIVE_BENCH)]))
    with ThreadPoolExecutor(max_workers=8) as pool:
        moves = dict(zip(symbols, pool.map(lambda s: move_since(s, published_at) if published_at else None, symbols), strict=True))
    for sym in chosen:
        ccy = native_currency(sym)
        broad = _is_index(sym) or sym in BROAD_ETFS
        bench = None if broad else BENCHMARK.get(ccy or "")
        m = moves.get(sym)
        b = moves.get(LIVE_BENCH[ccy]) if (m and bench) else None
        excess = round(m["move_pct"] - b["move_pct"], 2) if (m and b and m["traded"] and b["traded"]) else None
        out.append({"symbol": sym, "currency": ccy, "benchmark": bench, **(m or {}),
                    "bench_move_pct": b["move_pct"] if b else None, "excess_pct": excess,
                    "verdict": verdict(excess, hist) if hist else None})
    return {"article_id": article_id, "published_at": published_at, "approximate": approximate,
            "tickers": out, "history": hist}
