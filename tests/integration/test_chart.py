"""The stock panel's chart spans: Yahoo history on demand, stored closes when that fails."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from backend import history
from pipeline.db.models import PriceDaily
from tests.factories import add_prices


def _bars(day: datetime, closes: list[float], step_min: int = 5) -> list[tuple[datetime, float]]:
    return [(day + timedelta(minutes=step_min * i), c) for i, c in enumerate(closes)]


def test_one_day_is_the_latest_session_measured_from_the_previous_close(client, monkeypatch):
    ny = ZoneInfo("America/New_York")
    fri, mon = datetime(2026, 9, 25, 9, 30, tzinfo=ny), datetime(2026, 9, 28, 9, 30, tzinfo=ny)
    after_hours = (datetime(2026, 9, 25, 19, 0, tzinfo=ny), 90.0)  # not the close the day is measured from
    calls = []
    monkeypatch.setattr(history, "_download", lambda *a: calls.append(a) or [*_bars(fri, [100, 101, 99]), after_hours,
                                                                              *_bars(mon, [100, 104, 103, 102, 101, 105])])
    body = client.get("/chart/NVDA?span=1d").json()
    assert calls == [("NVDA", "5d", "5m", True)]  # with pre-market and after-hours
    assert body["source"] == "yahoo" and body["intraday"] is True
    assert body["candles"] == [100, 104, 103, 102, 101, 105] and body["base"] == 99  # Friday's regular close
    assert body["dates"][0].startswith("2026-09-28T09:30")

    client.get("/chart/NVDA?span=1d")
    assert len(calls) == 1  # cached while fresh


def test_a_day_that_has_barely_begun_shows_the_last_full_session(client, monkeypatch):
    ny = ZoneInfo("America/New_York")
    thu, fri, mon = (datetime(2026, 9, d, 9, 30, tzinfo=ny) for d in (24, 25, 28))
    monkeypatch.setattr(history, "_download", lambda *a: [*_bars(thu, [50]), *_bars(fri, [100, 101, 99, 98, 97, 96]), *_bars(mon, [95])])
    body = client.get("/chart/NVDA?span=1d").json()
    assert body["candles"] == [100, 101, 99, 98, 97, 96] and body["base"] == 50


def test_long_spans_use_daily_or_weekly_bars(client, monkeypatch):
    calls = []
    day = datetime(2025, 1, 6, tzinfo=UTC)
    monkeypatch.setattr(history, "_download", lambda *a: calls.append(a) or [(day + timedelta(days=7 * i), 50.0 + i) for i in range(5)])
    body = client.get("/chart/AAPL?span=5y").json()
    assert calls == [("AAPL", "5y", "1wk")]
    assert body["intraday"] is False and body["base"] == 50.0 and len(body["candles"]) == 5


def test_falls_back_to_stored_closes_when_yahoo_has_nothing(client, db_session):
    add_prices(db_session, "MSFT", [10.0, 11.0, 12.0])
    body = client.get("/chart/MSFT?span=1y").json()
    assert body["source"] == "stored" and body["candles"] == [10.0, 11.0, 12.0]
    assert client.get("/chart/NOPE?span=1d").json()["candles"] == []


def test_converts_every_point_or_none(client, db_session, monkeypatch):
    today = datetime.now(UTC).date()
    db_session.add(PriceDaily(ticker="USDINR=X", date=today - timedelta(days=1), close=80.0))
    db_session.commit()
    now = datetime.now(UTC)
    monkeypatch.setattr(history, "_download", lambda sym, *a: [] if sym.endswith("=X") else [(now - timedelta(minutes=10), 2.0), (now, 3.0)])
    inr = client.get("/chart/AAPL?span=5d&currency=INR").json()
    assert inr["currency"] == "INR" and inr["candles"] == [160.0, 240.0]
    # 1Y needs a year of rates: Yahoo has none here, so the chart stays in dollars rather than mixing.
    usd = client.get("/chart/AAPL?span=1y&currency=INR").json()
    assert usd["currency"] == "USD" and usd["candles"] == [2.0, 3.0]


def test_span_is_validated(client):
    assert client.get("/chart/AAPL?span=2w").status_code == 422
