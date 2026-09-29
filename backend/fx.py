"""
backend/fx.py
─────────────
Currency conversion for quotes and charts, from the daily USD rates the pipeline
stores beside prices (prices_daily rows like "USDINR=X": INR per 1 USD).

Rules that keep numbers honest:
  - a value is converted only when its native currency is known (index points never are);
  - each chart point uses that day's rate (the latest rate on or before the date);
  - when no rate is available the caller gets None and shows the native value instead.
"""
from __future__ import annotations

import bisect
import time
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from pipeline.db.models import PriceDaily
from pipeline.symbols import MINOR_UNITS

DISPLAY_CURRENCIES = ("USD", "INR")
MAX_RATE_GAP_DAYS = 7  # a rate older than this (weekends/holidays aside) is not used
_TTL_S = 300

_cache: dict[str, tuple[list[date], list[float]]] = {}
_loaded_at = 0.0


def _table(db: Session) -> dict[str, tuple[list[date], list[float]]]:
    """major currency → (sorted dates, units per 1 USD)."""
    global _cache, _loaded_at
    if time.monotonic() - _loaded_at < _TTL_S and _cache:
        return _cache
    rows = db.execute(
        select(PriceDaily.ticker, PriceDaily.date, PriceDaily.close)
        .where(PriceDaily.ticker.like("USD%=X"), PriceDaily.close.is_not(None), PriceDaily.close > 0)
        .order_by(PriceDaily.ticker, PriceDaily.date)
    ).all()
    table: dict[str, tuple[list[date], list[float]]] = {}
    for ticker, day, close in rows:
        ccy = ticker[3:-2]  # "USDINR=X" → "INR"
        dates, rates = table.setdefault(ccy, ([], []))
        dates.append(day)
        rates.append(float(close))
    _cache, _loaded_at = table, time.monotonic()
    return table


def reset_cache() -> None:
    global _cache, _loaded_at
    _cache, _loaded_at = {}, 0.0


def _per_usd(db: Session, major: str, on: date | None) -> tuple[float, date | None] | None:
    """Units of `major` per 1 USD on `on` (latest available when `on` is None)."""
    if major == "USD":
        return 1.0, None
    series = _table(db).get(major)
    if not series:
        return None
    dates, rates = series
    if on is None:
        return rates[-1], dates[-1]
    i = bisect.bisect_right(dates, on) - 1
    if i < 0 or (on - dates[i]).days > MAX_RATE_GAP_DAYS:
        return None
    return rates[i], dates[i]


def rate(db: Session, native: str, target: str, on: date | None = None) -> tuple[float, date | None] | None:
    """Multiplier from `native` amounts to `target` amounts (minor units like GBp handled)."""
    n_major, n_minor = MINOR_UNITS.get(native, (native, 1))
    t_major, t_minor = MINOR_UNITS.get(target, (target, 1))
    src, dst = _per_usd(db, n_major, on), _per_usd(db, t_major, on)
    if src is None or dst is None:
        return None
    as_of = max((d for d in (src[1], dst[1]) if d), default=None)
    return (dst[0] / src[0]) * (t_minor / n_minor), as_of
