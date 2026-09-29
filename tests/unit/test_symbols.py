import pytest

from pipeline.extract.prompt import normalize_extraction
from pipeline.symbols import canonical, is_us_listed, yahoo_symbol


@pytest.mark.parametrize(("news", "stored", "yahoo", "us"), [
    ("BTC", "BTC-USD", "BTC-USD", False),        # bare "BTC" is a US ETF; news means the coin
    ("eth-usd", "ETH-USD", "ETH-USD", False),
    ("NIFTY 50", "NIFTY", "^NSEI", False),
    ("^NSEI", "NIFTY", "^NSEI", False),
    ("BSESN", "SENSEX", "^BSESN", False),
    ("SPX", "SPX", "^GSPC", False),
    ("RELIANCE.NS", "RELIANCE.NS", "RELIANCE.NS", False),  # exchange suffix kept (was mangled to RELIANCE-NS)
    ("BRK.B", "BRK.B", "BRK-B", True),           # share class → Yahoo dash
    ("NVDA", "NVDA", "NVDA", True),
])
def test_symbol_vocabulary(news, stored, yahoo, us):
    assert canonical(news) == stored
    assert yahoo_symbol(stored) == yahoo
    assert is_us_listed(stored) is us


def test_extraction_stores_canonical_symbols():
    data = normalize_extraction({"tickers": ["BTC", "NIFTY 50", "NASDAQ:NVDA", "^BSESN"], "one_line": "x"})
    assert data["tickers"] == ["BTC-USD", "NIFTY", "NVDA", "SENSEX"]


def test_private_company_valuations_are_not_tickers():
    from pipeline.symbols import is_unlisted

    assert is_unlisted("ANTH.PVT") and not is_unlisted("NVDA")
    assert normalize_extraction({"tickers": ["ANTH.PVT", "NVDA"], "one_line": "x"})["tickers"] == ["NVDA"]
