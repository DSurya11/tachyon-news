"""
backend/history.py
──────────────────
Price history fetched from Yahoo when a chart asks for it, beyond the ~30 daily
closes the pipeline stores: intraday bars for 1D/5D, years of daily or weekly
bars for 1Y/5Y, and 5-minute bars around a headline for the priced-in meter.

Personal use only (Yahoo's terms). Results are cached per (symbol, span) for as
long as the bars stay current; a failed fetch is remembered briefly so a dead
symbol doesn't cost a request per view. Callers fall back to stored closes.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime

from cachetools import TTLCache

log = logging.getLogger(__name__)

Point = tuple[datetime, float]

# span: (Yahoo range, bar size, seconds the bars stay fresh, calendar days covered)
SPANS: dict[str, tuple[str, str, int, int]] = {
    "1d": ("5d", "5m", 120, 1),  # five days fetched so the previous session's close is known
    "5d": ("5d", "15m", 300, 7),
    "1m": ("1mo", "1d", 1800, 31),
    "3m": ("3mo", "1d", 3600, 92),
    "6m": ("6mo", "1d", 3600, 183),
    "1y": ("1y", "1d", 3600, 366),
    "5y": ("5y", "1wk", 6 * 3600, 1830),
}
INTRADAY = {"1d", "5d"}

_cache: TTLCache = TTLCache(maxsize=2000, ttl=6 * 3600)  # (ysym, period, interval) → (fetched_at, points)
_failed: TTLCache = TTLCache(maxsize=2000, ttl=60)
_lock = threading.Lock()


def _download(ysym: str, period: str, interval: str, prepost: bool = False) -> list[Point]:
    import yfinance as yf  # imported here: slow to import and only needed on a cache miss

    df = yf.Ticker(ysym).history(period=period, interval=interval, auto_adjust=False, prepost=prepost, timeout=10)
    if df is None or df.empty or "Close" not in df:
        return []
    return [(ts.to_pydatetime(), float(c)) for ts, c in df["Close"].items() if c == c and c > 0]  # c == c drops NaN


def bars(ysym: str, period: str, interval: str, fresh_s: int, prepost: bool = False) -> list[Point]:
    """Closes oldest first, timestamps in the exchange's time zone. [] when Yahoo has nothing.
    `prepost` adds US pre-market and after-hours bars (intraday intervals only)."""
    key = (ysym, period, interval, prepost)
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < fresh_s:
        return hit[1]
    if key in _failed:
        return hit[1] if hit else []
    try:
        points = _download(ysym, period, interval, *((True,) if prepost else ()))
    except Exception as exc:  # noqa: BLE001 — network, rate limit, yfinance parsing: all mean "no bars"
        log.info("History for %s (%s/%s) unavailable: %s", ysym, period, interval, exc)
        points = []
    with _lock:
        if points:
            _cache[key] = (time.monotonic(), points)
        else:
            _failed[key] = True
    return points or (hit[1] if hit else [])


def reset_cache() -> None:
    _cache.clear()
    _failed.clear()
