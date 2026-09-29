"""The dashboard's time range: windowed, server-filtered /news and the /summary aggregates."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pipeline.db.models import Report
from pipeline.market_time import ET
from tests.factories import add_article

NOW = datetime.now(UTC)


def _ago(**kw) -> datetime:
    return NOW - timedelta(**kw)


def _seed(db):
    return {
        "hour": add_article(db, id_hint="hour", published_at=_ago(hours=1), tickers=("NVDA",), sentiment="bullish"),
        "day2": add_article(db, id_hint="day2", published_at=_ago(hours=30), tickers=("NVDA", "AMD"), sentiment="bearish",
                            event_type="merger"),
        "week": add_article(db, id_hint="week", published_at=_ago(days=5), tickers=("JPM",), sector="Financials",
                            sentiment="neutral", status="extracted"),
        "old": add_article(db, id_hint="old", published_at=_ago(days=200), tickers=("AAPL",), sentiment="bullish",
                           one_line="Apple unveils a new chip"),
    }


def _ids(resp) -> list[str]:
    return [a["headline"].split()[-1] for a in resp.json()["articles"]]


def test_windows_default_to_all_time_and_accept_hours_days_and_dates(client, db_session):
    _seed(db_session)
    assert _ids(client.get("/news?limit=50")) == ["hour", "day2", "week", "old"]  # no window = all time
    assert _ids(client.get("/news?hours=24")) == ["hour"]
    assert _ids(client.get("/news?days=7")) == ["hour", "day2", "week"]
    since, until = _ago(days=6).isoformat(), _ago(hours=12).isoformat()
    assert _ids(client.get("/news", params={"since": since, "until": until})) == ["day2", "week"]
    assert client.get("/news", params={"since": NOW.isoformat(), "until": _ago(days=1).isoformat()}).status_code == 422
    assert client.get("/news?days=3000").status_code == 200  # long ranges are allowed now


def test_total_and_paging(client, db_session):
    _seed(db_session)
    first = client.get("/news?limit=3&page=1").json()
    assert (first["total"], first["has_more"], len(first["articles"])) == (4, True, 3)
    second = client.get("/news?limit=3&page=2").json()
    assert (second["total"], second["has_more"], len(second["articles"])) == (4, False, 1)


def test_server_side_filters(client, db_session):
    _seed(db_session)
    assert _ids(client.get("/news?sentiment=bearish")) == ["day2"]
    assert _ids(client.get("/news?sentiment=bullish,neutral&limit=50")) == ["hour", "week", "old"]
    assert _ids(client.get("/news?event=merger")) == ["day2"]
    assert _ids(client.get("/news?verified_only=true&limit=50")) == ["hour", "day2", "old"]
    assert _ids(client.get("/news?q=new chip")) == ["old"]  # searches the summary too
    assert client.get("/news?sentiment=euphoric").status_code == 422


def test_ids_ignore_the_window(client, db_session):
    s = _seed(db_session)
    resp = client.get("/news", params={"ids": f"{s['old'].id},{s['hour'].id}", "hours": 1})
    assert sorted(_ids(resp)) == ["hour", "old"]
    assert client.get("/news?ids=1,x").status_code == 422


def test_picks_are_ordered_by_pick_day_then_rank(client, db_session):
    s = _seed(db_session)
    today = datetime.now(ET).date()  # briefs are dated by the US trading day
    db_session.add_all([
        Report(trading_day=today - timedelta(days=1), content="x", article_ids=[],
               top_picks=[{"id": s["week"].id, "rank": 1, "why": "a"}]),
        Report(trading_day=today, content="y", article_ids=[],
               top_picks=[{"id": s["day2"].id, "rank": 2, "why": "b"}, {"id": s["hour"].id, "rank": 1, "why": "c"}]),
    ])
    db_session.commit()
    body = client.get("/news?picks=true&limit=50").json()
    assert [a["headline"].split()[-1] for a in body["articles"]] == ["hour", "day2", "week"]
    assert body["total"] == 3


def test_picks_follow_the_briefs_in_the_range(client, db_session):
    s = _seed(db_session)
    today = datetime.now(ET).date()
    db_session.add_all([
        Report(trading_day=today - timedelta(days=1), content="x", article_ids=[],
               top_picks=[{"id": s["week"].id, "rank": 1, "why": "a"}]),
        Report(trading_day=today, content="y", article_ids=[],
               top_picks=[{"id": s["day2"].id, "rank": 1, "why": "b"}]),
    ])
    db_session.commit()
    # A picked story counts by its brief's day, not its publish time (day2 came out 30h ago).
    assert _ids(client.get("/news?picks=true&hours=1")) == ["day2"]
    assert client.get("/summary?hours=1").json()["picks"] == 1
    assert _ids(client.get("/news?picks=true&hours=48")) == ["day2", "week"]
    # Nothing written yet in (or before) a range: no picks.
    long_ago = (datetime.now(UTC) - timedelta(days=400)).date()
    assert _ids(client.get(f"/news?picks=true&since={long_ago}T00:00:00Z&until={long_ago}T12:00:00Z")) == []


def test_summary_aggregates_the_window(client, db_session):
    _seed(db_session)
    day = client.get("/summary?hours=24").json()
    assert (day["count"], day["bullish"], day["verified"]) == (1, 1, 1)
    assert day["timeline"]["unit"] == "hour" and len(day["timeline"]["buckets"]) in (24, 25)
    week = client.get("/summary?days=7").json()
    assert (week["count"], week["bullish"], week["neutral"], week["bearish"], week["verified"]) == (3, 1, 1, 1, 2)
    assert [t["symbol"] for t in week["tickers"]] == ["NVDA", "AMD", "JPM"]
    nvda = week["tickers"][0]
    assert (nvda["count"], nvda["bullish"], nvda["bearish"]) == (2, 1, 1)
    assert nvda["latest"]["headline"] == "Headline hour"
    assert {s["name"]: s["count"] for s in week["sectors"]} == {"Technology": 2, "Financials": 1}
    assert week["timeline"]["unit"] == "day"
    everything = client.get("/summary").json()
    assert everything["count"] == 4 and everything["timeline"]["unit"] == "day"


def test_summary_always_includes_requested_symbols(client, db_session):
    _seed(db_session)
    body = client.get("/summary?hours=24&top=0&symbols=nvda,TSLA").json()
    by = {t["symbol"]: t for t in body["tickers"]}
    assert by["NVDA"]["count"] == 1
    assert by["TSLA"]["count"] == 0 and by["TSLA"]["latest"] is None  # a watched ticker with no news


def test_summary_market_filter(client, db_session):
    _seed(db_session)
    add_article(db_session, id_hint="india", published_at=_ago(hours=2), tickers=("RELIANCE.NS",), market="india")
    assert client.get("/summary?hours=24&market=india").json()["count"] == 1
    assert client.get("/summary?hours=24&market=global").json()["count"] == 1


def test_timeline_bar_size_follows_the_span(client, db_session):
    _seed(db_session)
    units = {h: client.get(f"/summary?hours={h}").json()["timeline"] for h in (1, 6, 24, 24 * 7)}
    assert [units[h]["unit"] for h in (1, 6, 24, 24 * 7)] == ["5min", "15min", "hour", "day"]
    assert 12 <= len(units[1]["buckets"]) <= 13 and 24 <= len(units[6]["buckets"]) <= 25
    assert sum(b["bullish"] for b in units[1]["buckets"]) == 0  # the 1-hour-old story sits at the edge
    assert sum(b["bullish"] for b in units[24]["buckets"]) == 1


def test_timeline_starts_at_the_first_story(client, db_session):
    add_article(db_session, id_hint="only", published_at=_ago(days=3))
    db_session.commit()
    tl = client.get("/summary?days=365").json()["timeline"]
    assert tl["unit"] == "hour"  # three days of data, not a year of empty days
    assert 72 <= len(tl["buckets"]) <= 74
