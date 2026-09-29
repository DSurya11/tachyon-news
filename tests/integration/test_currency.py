"""Quotes and charts carry their currency, and convert only when the result is known to be right."""
from datetime import date, timedelta

import pytest

from pipeline.db.models import PriceDaily


def _prices(session, ticker, rows):
    for day, close in rows:
        session.add(PriceDaily(ticker=ticker, date=day, open=close, high=close, low=close, close=close, volume=0))
    session.commit()


D0 = date.today() - timedelta(days=1)
D1 = date.today()


@pytest.fixture
def market(db_session):
    _prices(db_session, "USDINR=X", [(D0, 80.0), (D1, 84.0)])   # INR per USD moved between the two days
    _prices(db_session, "USDGBP=X", [(D0, 0.8), (D1, 0.8)])
    _prices(db_session, "RELIANCE.NS", [(D0, 2400.0), (D1, 2520.0)])
    _prices(db_session, "NVDA", [(D0, 100.0), (D1, 110.0)])
    _prices(db_session, "TSCO.L", [(D0, 300.0), (D1, 320.0)])  # pence
    _prices(db_session, "NIFTY", [(D0, 22000.0), (D1, 22100.0)])
    _prices(db_session, "KNG.TO", [(D0, 10.0), (D1, 11.0)])     # CAD, but no USDCAD rate stored


def _q(client, sym, ccy):
    return client.get(f"/quote/{sym}?currency={ccy}").json()


def test_quotes_are_labelled_and_converted_at_the_latest_rate(client, market):
    native = _q(client, "RELIANCE.NS", "native")
    assert (native["price"], native["currency"]) == (2520.0, "INR")
    usd = _q(client, "RELIANCE.NS", "USD")
    assert usd["currency"] == "USD" and usd["native_currency"] == "INR"
    assert usd["price"] == pytest.approx(2520 / 84) and usd["fx_rate"] == pytest.approx(1 / 84)
    assert usd["pct_change"] == native["pct_change"]  # the listing's own move, not an FX artefact
    inr = _q(client, "NVDA", "INR")
    assert (inr["price"], inr["currency"]) == (pytest.approx(110 * 84), "INR")
    assert _q(client, "NVDA", "USD")["price"] == 110.0  # already USD: untouched


def test_pence_are_converted_to_whole_currency(client, market):
    assert _q(client, "TSCO.L", "native")["currency"] == "GBp"
    assert _q(client, "TSCO.L", "USD")["price"] == pytest.approx(320 / 100 / 0.8)  # 320p = £3.20 = $4.00


def test_index_points_and_missing_rates_are_never_converted(client, market):
    nifty = _q(client, "NIFTY", "USD")
    assert (nifty["price"], nifty["currency"], nifty["unit"]) == (22100.0, None, "pts")
    cad = _q(client, "KNG.TO", "INR")
    assert (cad["price"], cad["currency"], cad["fx_unavailable"]) == (11.0, "CAD", True)
    batch = {q["symbol"]: q for q in client.get("/quotes?symbols=NVDA,NIFTY&currency=INR").json()["data"]}
    assert batch["NVDA"]["currency"] == "INR" and batch["NIFTY"]["currency"] is None


def test_charts_convert_each_day_at_that_days_rate(client, market):
    c = client.get("/candles/RELIANCE.NS?currency=USD").json()
    assert c["currency"] == "USD"
    assert c["candles"] == [pytest.approx(2400 / 80), pytest.approx(2520 / 84)]
    assert client.get("/candles/RELIANCE.NS").json()["candles"] == [2400.0, 2520.0]
    # No rate for CAD → the whole chart stays in CAD rather than mixing currencies.
    assert client.get("/candles/KNG.TO?currency=USD").json()["currency"] == "CAD"
    assert client.get("/candles/NIFTY?currency=INR").json()["unit"] == "pts"
    assert client.get("/quote/NVDA?currency=EUR").status_code == 422
