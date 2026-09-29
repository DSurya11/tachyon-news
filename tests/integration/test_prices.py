"""The price stage must cover every ticker the dashboard shows — including LLM-only ones."""
import contextlib

import pandas as pd

from pipeline.db.local import LocalSession
from pipeline.db.models import Extraction, PriceDaily
from pipeline.db.schema import ensure_schema
from pipeline.prices import yahoo
from tests.factories import add_article


def test_llm_only_tickers_get_price_history(monkeypatch, db_session):
    art = add_article(db_session, tickers=("NVDA",))  # NVDA is Finviz-tagged
    db_session.query(Extraction).filter_by(article_id=art.id).update({"tickers": ["NVDA", "RELIANCE.NS", "BTC-USD", "NIFTY"]})
    db_session.commit()

    asked: list[str] = []

    def fake_download(symbols, **kw):
        asked.extend(symbols)
        idx = pd.to_datetime(["2026-09-25", "2026-09-28"])
        cols = pd.MultiIndex.from_product([symbols, ["Open", "High", "Low", "Close", "Volume"]])
        return pd.DataFrame([[1.0, 2.0, 0.5, 1.5, 10] * len(symbols)] * 2, index=idx, columns=cols)

    monkeypatch.setattr(yahoo.yf, "download", fake_download)
    yahoo.update_prices()
    # Yahoo's names, plus the INR rate the dashboard converts with and the S&P 500 benchmark (outcomes).
    assert sorted(asked) == ["BTC-USD", "NVDA", "RELIANCE.NS", "USDINR=X", "^GSPC", "^NSEI"]
    with LocalSession() as s:
        stored = {t for (t,) in s.query(PriceDaily.ticker).distinct()}
    assert stored == {"BTC-USD", "NVDA", "RELIANCE.NS", "NIFTY", "SPX", "USDINR=X"}  # the dashboard's names


def test_schema_upgrade_rewrites_legacy_llm_tickers(engine, db_session):
    art = add_article(db_session, tickers=())
    db_session.query(Extraction).filter_by(article_id=art.id).update({"tickers": ["BTC", "NSEI", "AAPL"]})
    db_session.commit()
    ensure_schema(engine)
    db_session.expire_all()
    assert db_session.query(Extraction).filter_by(article_id=art.id).one().tickers == ["BTC-USD", "NIFTY", "AAPL"]


def _yahoo_knows(monkeypatch, known: set[str]):
    def fake_download(symbols, **kw):
        have = [s for s in symbols if s in known]
        if not have:
            return pd.DataFrame()
        idx = pd.to_datetime(["2026-09-25", "2026-09-28"])
        cols = pd.MultiIndex.from_product([have, ["Open", "High", "Low", "Close", "Volume"]])
        return pd.DataFrame([[1.0, 2.0, 0.5, 1.5, 10] * len(have)] * 2, index=idx, columns=cols)
    monkeypatch.setattr(yahoo.yf, "download", fake_download)


def test_invented_symbols_are_hidden_after_two_failed_checks(monkeypatch, db_session, client):
    from pipeline.db.models import SymbolCheck

    art = add_article(db_session, tickers=("NVDA",), headline="NSE plans IPO")
    db_session.query(Extraction).filter_by(article_id=art.id).update({"tickers": ["NVDA", "NSE.NS"]})
    db_session.commit()
    _yahoo_knows(monkeypatch, {"NVDA", "USDINR=X"})

    assert client.get("/news").json()["articles"][0]["tickers"] == ["NSE.NS", "NVDA"]  # not checked yet
    yahoo.update_prices()  # first miss: hidden at once, but only "pending"
    assert client.get("/news").json()["articles"][0]["tickers"] == ["NVDA"]
    with LocalSession() as s:
        assert s.get(SymbolCheck, "NSE.NS").status == "pending"
    yahoo.update_prices()  # second miss: invalid (no longer fetched until the weekly recheck)
    with LocalSession() as s:
        assert s.get(SymbolCheck, "NSE.NS").status == "invalid"
        assert s.get(SymbolCheck, "NVDA").status == "valid"


def test_a_real_symbol_hit_by_a_hiccup_comes_back(monkeypatch, db_session, client):
    art = add_article(db_session, tickers=("NVDA",))
    db_session.query(Extraction).filter_by(article_id=art.id).update({"tickers": ["NVDA", "RELIANCE.NS"]})
    db_session.commit()
    _yahoo_knows(monkeypatch, {"NVDA", "USDINR=X"})  # Reliance missing this run only
    yahoo.update_prices()
    assert client.get("/news").json()["articles"][0]["tickers"] == ["NVDA"]
    _yahoo_knows(monkeypatch, {"NVDA", "USDINR=X", "RELIANCE.NS"})
    yahoo.update_prices()
    assert client.get("/news").json()["articles"][0]["tickers"] == ["NVDA", "RELIANCE.NS"]


def test_a_yahoo_outage_never_invalidates_symbols(monkeypatch, db_session):
    from pipeline.db.models import SymbolCheck

    add_article(db_session, tickers=("NVDA",))
    _yahoo_knows(monkeypatch, set())  # Yahoo returns nothing at all
    for _ in range(3):
        with contextlib.suppress(RuntimeError):  # "yfinance returned no price data" — expected in an outage
            yahoo.update_prices()
    with LocalSession() as s:
        assert s.query(SymbolCheck).count() == 0
