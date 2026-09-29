"""
pipeline/prices/outcomes.py
───────────────────────────
What each story's stocks did next, from the stored daily closes: the return from the
last close before the headline to the first close after it (day 0), one session later
(+1d) and five sessions later (+5d), beside the benchmark's return over the same days
(S&P 500 for US listings, Nifty 50 for Indian ones).

These rows are the history behind the priced-in meter ("news like this usually fades
or keeps going"). Horizons fill in as their sessions close; a row is final once +5d is
known. Only sessions that have closed count, so a price fetched mid-session is never
mistaken for a close.
"""
from __future__ import annotations

import bisect
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from pipeline.db.local import LocalSession
from pipeline.db.models import Article, EventOutcome, Extraction, PriceDaily
from pipeline.db.queries import article_tickers
from pipeline.symbols import native_currency

log = logging.getLogger(__name__)

# listing currency → benchmark, and when that market's session closes
BENCHMARK = {"USD": "SPX", "INR": "NIFTY"}
SESSION_CLOSE = {"SPX": (time(16, 0), ZoneInfo("America/New_York")), "NIFTY": (time(15, 30), ZoneInfo("Asia/Kolkata"))}
SETTLE = timedelta(minutes=30)  # a close is final this long after the bell (the hourly price run re-fetches it)
MAX_TICKERS = 3  # stories naming more are round-ups, not news about a company
LOOKBACK_DAYS = 60
HORIZONS = {"ret_day0": 0, "ret_1d": 1, "ret_5d": 5}  # sessions after day 0


@dataclass(frozen=True)
class Series:
    dates: list[date]
    closes: list[float]

    def on_or_before(self, day: date) -> float | None:
        i = bisect.bisect_right(self.dates, day) - 1
        return self.closes[i] if i >= 0 and (day - self.dates[i]).days <= 4 else None


def outcome(published_at: datetime, stock: Series, bench: Series | None, benchmark: str, now: datetime) -> dict | None:
    """Returns for one story and ticker, or None when there's no close before and after the headline yet."""
    close_at, tz = SESSION_CLOSE[benchmark]

    def closed(d: date) -> datetime:
        return datetime.combine(d, close_at, tz)

    settled = [i for i, d in enumerate(stock.dates) if closed(d) + SETTLE <= now]
    after = [i for i in settled if closed(stock.dates[i]) >= published_at]
    if not after or after[0] == 0:
        return None
    i0 = after[0]
    base = i0 - 1
    last_settled = settled[-1]
    b_base = bench.on_or_before(stock.dates[base]) if bench else None
    row = {"base_date": stock.dates[base], "day0_date": stock.dates[i0]}
    for col, k in HORIZONS.items():
        i = i0 + k
        ok = i <= last_settled
        row[col] = stock.closes[i] / stock.closes[base] - 1 if ok else None
        b = bench.on_or_before(stock.dates[i]) if (ok and bench and b_base) else None
        row[col.replace("ret_", "bench_")] = b / b_base - 1 if b else None
    return row


def _series(session, symbols: set[str], since: date) -> dict[str, Series]:
    rows = session.execute(
        select(PriceDaily.ticker, PriceDaily.date, PriceDaily.close)
        .where(PriceDaily.ticker.in_(symbols), PriceDaily.date >= since, PriceDaily.close.is_not(None), PriceDaily.close > 0)
        .order_by(PriceDaily.ticker, PriceDaily.date)
    ).all()
    out: dict[str, tuple[list, list]] = {}
    for t, d, c in rows:
        ds, cs = out.setdefault(t, ([], []))
        ds.append(d)
        cs.append(float(c))
    return {t: Series(ds, cs) for t, (ds, cs) in out.items()}


def compute_outcomes(now: datetime | None = None) -> dict:
    """Fill in every horizon that has closed for stories of the last LOOKBACK_DAYS."""
    now = now or datetime.now(UTC)
    since = now - timedelta(days=LOOKBACK_DAYS)
    with LocalSession() as session:
        stories = session.execute(
            select(Article.id, Article.published_at, Extraction.event_type, Extraction.sentiment, Extraction.tickers)
            .join(Extraction, Extraction.article_id == Article.id)
            .where(Article.published_at >= since, Article.published_at <= now)
        ).all()
        final = set(session.execute(
            select(EventOutcome.article_id, EventOutcome.ticker).where(EventOutcome.ret_5d.is_not(None))
        ).all())
        tickers = article_tickers(session, [s.id for s in stories], {s.id: s.tickers for s in stories})
        wanted = {
            s.id: [t for t in tickers[s.id] if BENCHMARK.get(native_currency(t) or "") and t not in SESSION_CLOSE]
            for s in stories
            if 1 <= len(tickers[s.id]) <= MAX_TICKERS
        }
        prices = _series(session, {t for ts in wanted.values() for t in ts} | set(SESSION_CLOSE), since.date() - timedelta(days=10))

        rows = []
        for s in stories:
            for t in wanted.get(s.id, []):
                if (s.id, t) in final or t not in prices:
                    continue
                benchmark = BENCHMARK[native_currency(t)]
                r = outcome(s.published_at, prices[t], prices.get(benchmark), benchmark, now)
                if r:
                    rows.append({"article_id": s.id, "ticker": t, "benchmark": benchmark, "event_type": s.event_type,
                                 "sentiment": s.sentiment, "published_at": s.published_at, "computed_at": now, **r})
        for i in range(0, len(rows), 1000):
            stmt = insert(EventOutcome).values(rows[i : i + 1000])
            session.execute(stmt.on_conflict_do_update(
                index_elements=["article_id", "ticker"],
                set_={c: stmt.excluded[c] for c in ("event_type", "sentiment", "base_date", "day0_date", *HORIZONS,
                                                    "bench_day0", "bench_1d", "bench_5d", "computed_at")},
            ))
        session.commit()
    done = sum(r["ret_5d"] is not None for r in rows)
    log.info("Outcomes: %d story-ticker rows updated (%d now final at +5d)", len(rows), done)
    return {"rows": len(rows), "final": done}
