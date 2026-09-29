"""The priced-in meter endpoint: live move beyond the market, and history only once it's earned."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from backend import history, reaction
from pipeline.db.models import EventOutcome
from tests.factories import add_article


def _outcomes(db, article, n: int, days: int, day0: float, d5: float):
    for i in range(n):
        db.add(EventOutcome(article_id=article.id, ticker=f"T{i}", benchmark="SPX", event_type="earnings", sentiment="bearish",
                            base_date=date(2026, 9, 1), day0_date=date(2026, 9, 1) + timedelta(days=i % days),
                            ret_day0=day0, bench_day0=0, ret_1d=d5, bench_1d=0, ret_5d=d5, bench_5d=0))
    db.commit()


def test_move_since_headline_beyond_the_market(client, db_session, monkeypatch):
    published = datetime.now(UTC) - timedelta(hours=2)
    art = add_article(db_session, id_hint="r", tickers=("NVDA",), sentiment="bearish", event_type="earnings", published_at=published)
    db_session.commit()
    t = published - timedelta(minutes=30)
    bars = {"NVDA": [(t, 100.0), (t + timedelta(minutes=5), 100.0), (published + timedelta(minutes=30), 96.0)],
            "SPY": [(t, 50.0), (t + timedelta(minutes=5), 50.0), (published + timedelta(minutes=30), 49.5)]}
    monkeypatch.setattr(history, "_download", lambda sym, *a: bars.get(sym, []))
    body = client.get(f"/news/{art.id}/reaction").json()
    nv = body["tickers"][0]
    assert nv["symbol"] == "NVDA" and nv["t0_price"] == 100.0 and nv["move_pct"] == -4.0
    assert nv["benchmark"] == "SPX" and nv["bench_move_pct"] == -1.0 and nv["excess_pct"] == -3.0
    assert body["history"]["horizon"] is None and nv["verdict"] is None  # no history yet


def test_history_needs_enough_samples_over_enough_days(client, db_session):
    art = add_article(db_session, id_hint="h", sentiment="bearish", event_type="earnings")
    db_session.commit()
    _outcomes(db_session, art, n=30, days=2, day0=-0.02, d5=-0.03)
    assert reaction.group_history(db_session, "earnings", "bearish")["horizon"] is None  # 30 samples, 2 days
    reaction._group_cache.clear()
    db_session.query(EventOutcome).delete()
    _outcomes(db_session, art, n=30, days=6, day0=-0.02, d5=-0.03)
    h = reaction.group_history(db_session, "earnings", "bearish")
    assert h["horizon"] == "5d" and h["n"] == 30 and h["median"] == -3.0 and h["day0_median"] == -2.0
    assert h["kept_going"] == 100  # every first-day drop deepened by day 5


def test_unknown_story_is_404(client):
    assert client.get("/news/999999/reaction").status_code == 404


def test_market_itself_has_no_benchmark_and_stocks_come_first(client, db_session, monkeypatch):
    published = datetime.now(UTC) - timedelta(hours=2)
    art = add_article(db_session, id_hint="m", tickers=("SPX", "SPY", "AAPL"), sentiment="bearish", event_type="macro",
                      published_at=published)
    db_session.commit()
    t = published - timedelta(minutes=30)
    monkeypatch.setattr(history, "_download", lambda sym, *a: [(t, 10.0), (t + timedelta(minutes=5), 10.0), (published + timedelta(minutes=30), 11.0)])
    rows = client.get(f"/news/{art.id}/reaction").json()["tickers"]
    assert [r["symbol"] for r in rows] == ["AAPL", "SPY", "SPX"]
    assert rows[0]["benchmark"] == "SPX" and rows[1]["benchmark"] is None and rows[2]["benchmark"] is None
    assert rows[1]["move_pct"] == 10.0 and rows[1]["excess_pct"] is None
