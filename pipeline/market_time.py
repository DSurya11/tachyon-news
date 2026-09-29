"""
pipeline/market_time.py
───────────────────────
US trading-day helpers shared by the scraper, report and API.

Rule: a trading day closes at 4 PM ET.  News published at/after the close
belongs to the next trading day, and weekend news rolls forward to Monday.
Exchange holidays are not modelled; news on a holiday simply forms its own
(quiet) "trading day".
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytz

ET = pytz.timezone("America/New_York")
MARKET_CLOSE_HOUR_ET = 16


def compute_trading_day(published_at: datetime | None) -> date | None:
    """Map a publish timestamp to the US trading day it informs."""
    if published_at is None:
        return None
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=UTC)
    et = published_at.astimezone(ET)
    day = et.date()
    if et.hour >= MARKET_CLOSE_HOUR_ET:
        day += timedelta(days=1)
    # Saturday (5) → Monday, Sunday (6) → Monday
    if day.weekday() >= 5:
        day += timedelta(days=7 - day.weekday())
    return day


def current_trading_day(now: datetime | None = None) -> date:
    """The trading day that news arriving right now belongs to."""
    day = compute_trading_day(now or datetime.now(UTC))
    assert day is not None
    return day
