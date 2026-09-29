from datetime import date, timedelta

from pipeline.db.models import Report, ScrapeRun
from tests.factories import NOW, add_article, add_prices


def test_health_reports_freshness_and_readiness(client, db_session):
    db_session.add(ScrapeRun(started_at=NOW, status="done", items_found=90, error_count=0))
    db_session.commit()
    add_article(db_session)
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["items_found"] == 90
    assert body["days_with_data"] == 1
    assert 0 < body["readiness"] <= 100


def test_health_is_degraded_without_recent_scrapes(client):
    assert client.get("/health").json()["status"] == "degraded"


def test_news_feed_shape_and_filters(client, db_session):
    add_article(db_session, id_hint="a", tickers=("NVDA",), sector="Technology")
    add_article(db_session, id_hint="b", tickers=("JPM",), sector="Financials", status="extracted")
    add_article(db_session, id_hint="c", tickers=(), extraction=True, headline="Fed holds rates")
    add_article(db_session, id_hint="d", status="extraction_failed", extraction=False)

    r = client.get("/news")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "private, max-age=60"
    arts = r.json()["articles"]
    assert len(arts) == 3  # failed extraction excluded by default
    first = next(a for a in arts if a["headline"] == "Headline a")
    assert first["url"] == "https://Example.com/Story-a"
    assert first["sector"] == "Technology" and first["verified"] is True
    assert first["tickers"] == ["NVDA"]

    assert [a["headline"] for a in client.get("/news?sector=Financials").json()["articles"]] == ["Headline b"]
    assert [a["headline"] for a in client.get("/news?sector=Macro %26 Markets").json()["articles"]] == ["Fed holds rates"]
    assert [a["headline"] for a in client.get("/news?ticker=nvda").json()["articles"]] == ["Headline a"]
    assert [a["headline"] for a in client.get("/news?q=fed").json()["articles"]] == ["Fed holds rates"]
    assert len(client.get("/news?status=extraction_failed").json()["articles"]) == 1
    assert client.get("/news?status=bogus").status_code == 422


def test_news_pagination(client, db_session):
    for i in range(5):
        add_article(db_session, id_hint=str(i), published_at=NOW - timedelta(minutes=i))
    p1 = client.get("/news?limit=2&page=1").json()
    p3 = client.get("/news?limit=2&page=3").json()
    assert [a["headline"] for a in p1["articles"]] == ["Headline 0", "Headline 1"] and p1["has_more"]
    assert [a["headline"] for a in p3["articles"]] == ["Headline 4"] and not p3["has_more"]


def test_article_detail(client, db_session):
    art = add_article(db_session)
    body = client.get(f"/news/{art.id}").json()
    assert body["extraction"]["one_line"] == "Summary 1"
    assert client.get("/news/999999").status_code == 404


def test_sectors(client, db_session):
    add_article(db_session, id_hint="a", tickers=("NVDA",), sector="Technology")
    add_article(db_session, id_hint="b", tickers=("AMD",), sector="Technology")
    add_article(db_session, id_hint="c", tickers=("JPM",), sector="Financials")
    assert client.get("/sectors").json()["sectors"] == [
        {"name": "Technology", "count": 2},
        {"name": "Financials", "count": 1},
    ]


def test_reports(client, db_session):
    assert client.get("/reports/latest").status_code == 404
    db_session.add_all([
        Report(trading_day=date(2026, 9, 24), content="Older", article_ids=[1], provider="omniroute"),
        Report(trading_day=date(2026, 9, 25), content="Market is doing well", article_ids=[1, 2], provider="anthropic"),
    ])
    db_session.commit()
    latest = client.get("/reports/latest").json()
    assert latest["content"] == "Market is doing well"
    assert "provider" not in latest and all("provider" not in r for r in client.get("/reports").json()["reports"])
    assert client.get("/reports/2026-09-24").json()["content"] == "Older"
    assert client.get("/reports/2026-01-01").status_code == 404
    assert [r["trading_day"] for r in client.get("/reports").json()["reports"]] == ["2026-09-25", "2026-09-24"]


def test_quotes_fall_back_to_daily_close_without_finnhub(client, db_session):
    add_prices(db_session, "AAPL", [100.0, 110.0])
    q = client.get("/quote/aapl").json()
    assert q == {"symbol": "AAPL", "price": 110.0, "change": 10.0, "pct_change": 10.0, "currency": "USD", "native_currency": "USD",
                 "as_of": q["as_of"], "stale": True, "source": "daily_close"}
    assert client.get("/quote/ZZZZ").status_code == 404
    assert client.get("/quote/bad!").status_code == 422
    batch = client.get("/quotes?symbols=AAPL,ZZZZ,AAPL").json()["data"]
    assert [b.get("price", b.get("error")) for b in batch] == [110.0, "No quote available"]
    assert client.get("/quotes?symbols=" + ",".join(f"A{i}" for i in range(51))).status_code == 400


def test_candles(client, db_session):
    add_prices(db_session, "NVDA", [1.0, 2.0, 3.0])
    body = client.get("/candles/NVDA?days=2").json()
    assert body["candles"] == [2.0, 3.0] and len(body["dates"]) == 2


def test_stats_and_root(client, db_session):
    add_article(db_session)
    assert client.get("/stats").json()["articles_by_status"] == {"verified": 1}
    assert client.get("/").json()["docs"] == "/docs"


def test_finnhub_rate_limit_pauses_calls_and_falls_back(client, db_session, monkeypatch):
    import httpx

    from backend.routers import quotes

    add_prices(db_session, "AAPL", [100.0, 110.0])
    calls = []

    async def fake_get(self, url, params=None):
        calls.append(params["symbol"])
        return httpx.Response(429, request=httpx.Request("GET", url))

    monkeypatch.setattr(quotes.settings, "finnhub_api_key", "test-key")
    monkeypatch.setattr(quotes, "_finnhub_paused_until", 0.0)
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    first = client.get("/quote/AAPL").json()
    assert first["source"] == "daily_close" and calls == ["AAPL"]
    quotes._quote_cache.clear()
    client.get("/quote/AAPL")
    assert calls == ["AAPL"]  # paused: no second Finnhub call


def test_market_filter_and_llm_sector_fallback(client, db_session):
    from pipeline.db.models import Extraction

    add_article(db_session, id_hint="us", tickers=("NVDA",), sector="Technology")
    india = add_article(db_session, id_hint="in", tickers=(), market="india", headline="Sensex falls")
    db_session.query(Extraction).filter_by(article_id=india.id).update({"sector": "Financials", "tickers": ["HDFCBANK.NS"]})
    db_session.commit()

    everything = client.get("/news").json()["articles"]
    assert {a["market"] for a in everything} == {"global", "india"}
    only_india = client.get("/news?market=india").json()["articles"]
    assert [a["headline"] for a in only_india] == ["Sensex falls"]
    assert only_india[0]["sector"] == "Financials" and only_india[0]["tickers"] == ["HDFCBANK.NS"]
    assert [a["headline"] for a in client.get("/news?market=global").json()["articles"]] == ["Headline us"]
    assert client.get("/news?market=mars").status_code == 422
    assert [s["name"] for s in client.get("/sectors?market=india").json()["sectors"]] == ["Financials"]


def test_top_picks_are_attached_to_stories(client, db_session):
    a = add_article(db_session, id_hint="a")
    add_article(db_session, id_hint="b")
    db_session.add(Report(trading_day=date.today(), content="## Brief", article_ids=[a.id],
                          top_picks=[{"id": a.id, "rank": 1, "why": "Sets the tone"}]))
    db_session.commit()
    arts = {x["headline"]: x for x in client.get("/news").json()["articles"]}
    assert arts["Headline a"]["top_pick"] == {"rank": 1, "why": "Sets the tone", "trading_day": date.today().isoformat()}
    assert arts["Headline b"]["top_pick"] is None
    assert client.get("/reports/latest").json()["top_picks"][0]["id"] == a.id


def test_batch_quotes_tolerate_bad_symbols(client, db_session):
    add_prices(db_session, "RELIANCE.NS", [2900.0, 2950.0])
    data = {q["symbol"]: q for q in client.get("/quotes?symbols=RELIANCE.NS,bad!,ZZZZ").json()["data"]}
    assert data["RELIANCE.NS"]["price"] == 2950.0 and data["RELIANCE.NS"]["stale"] is True
    assert data["BAD!"]["error"] == "Invalid symbol" and "error" in data["ZZZZ"]


def test_responses_carry_security_headers(anon_client):
    headers = anon_client.get("/health").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "no-referrer"
