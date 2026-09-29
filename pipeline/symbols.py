"""
pipeline/symbols.py
───────────────────
One vocabulary for ticker symbols across extraction, prices and quotes.

The LLM writes symbols the way news does: "BTC", "NIFTY", "Sensex", "RELIANCE.NS".
`canonical()` turns those into the symbol stored and shown by the dashboard, and
`yahoo_symbol()` into the one yfinance understands:

    BTC / BTC-USD      → BTC-USD      (Yahoo BTC-USD; bare "BTC" is an ETF on US exchanges)
    NIFTY / NSEI       → NIFTY        (Yahoo ^NSEI)
    SENSEX / BSESN     → SENSEX       (Yahoo ^BSESN)
    RELIANCE.NS        → RELIANCE.NS  (Yahoo RELIANCE.NS)
    BRK.B              → BRK.B        (Yahoo BRK-B)
"""
from __future__ import annotations

import re

# Major coins. Bare symbols that collide with US equities in practice (LINK, DOT…)
# are left alone: the LLM only sees them in crypto stories if it writes COIN-USD.
CRYPTO = frozenset({"BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "BNB", "AVAX", "LTC", "SHIB", "TRX", "TON", "XLM", "BCH"})

# Index names as they appear in news → (dashboard symbol, Yahoo symbol).
INDICES: dict[str, tuple[str, str]] = {}
for aliases, canon, yahoo in [
    (("NIFTY", "NIFTY50", "NIFTY 50", "NSEI", "NIFTY.NS", "NIFTY50.NS", "^NSEI"), "NIFTY", "^NSEI"),
    (("BANKNIFTY", "NIFTYBANK", "NSEBANK", "BANK NIFTY", "^NSEBANK"), "BANKNIFTY", "^NSEBANK"),
    (("SENSEX", "BSESN", "SENSEX.BO", "^BSESN"), "SENSEX", "^BSESN"),
    (("SPX", "GSPC", "S&P500", "^GSPC"), "SPX", "^GSPC"),
    (("DJI", "DJIA", "^DJI"), "DJI", "^DJI"),
    (("NDX", "^NDX"), "NDX", "^NDX"),
    (("IXIC", "COMPOSITE", "^IXIC"), "IXIC", "^IXIC"),
    (("VIX", "^VIX"), "VIX", "^VIX"),
    (("NIKKEI", "N225", "NIKKEI225", "^N225"), "NIKKEI", "^N225"),
    (("HSI", "HANGSENG", "^HSI"), "HSI", "^HSI"),
    (("DAX", "GDAXI", "^GDAXI"), "DAX", "^GDAXI"),
    (("FTSE", "FTSE100", "^FTSE"), "FTSE", "^FTSE"),
    (("KOSPI", "KS11", "^KS11"), "KOSPI", "^KS11"),
    (("SSEC", "SHCOMP", "000001.SS"), "SSEC", "000001.SS"),
]:
    for alias in aliases:
        INDICES[alias] = (canon, yahoo)
_YAHOO_INDEX = {canon: yahoo for canon, yahoo in INDICES.values()}

# US share classes (BRK.B, LEN.B). One-letter *exchange* suffixes are excluded: .L London, .V TSX Venture, .T Tokyo.
_SHARE_CLASS_RE = re.compile(r"^[A-Z]+\.[A-KM-SUW-Z]$")


# Yahoo's private-company valuations (ANTH.PVT, OPAI.PVT) look like tickers but don't trade.
UNLISTED_SUFFIXES = (".PVT",)


def is_unlisted(symbol: str) -> bool:
    """A symbol that names something without a market listing (never shown as a ticker)."""
    return symbol.endswith(UNLISTED_SUFFIXES)


def canonical(symbol: str) -> str:
    """The dashboard's symbol for what the news called `symbol` (already upper-cased)."""
    sym = symbol.strip().upper()
    if sym in INDICES:
        return INDICES[sym][0]
    if sym in CRYPTO:
        return f"{sym}-USD"
    return sym


def yahoo_symbol(symbol: str) -> str:
    """yfinance's symbol for a dashboard symbol."""
    if symbol in _YAHOO_INDEX:
        return _YAHOO_INDEX[symbol]
    if _SHARE_CLASS_RE.match(symbol):
        return symbol.replace(".", "-")  # BRK.B → BRK-B; exchange suffixes (.NS, .TO) stay as they are
    return symbol


def is_us_listed(symbol: str) -> bool:
    """True for plain US equities/ETFs — the only symbols Finnhub's free tier quotes."""
    return native_currency(symbol) == "USD" and not symbol.endswith("-USD")


# ---------------------------------------------------------------------------
# Currencies
# ---------------------------------------------------------------------------

# Yahoo exchange suffix → the currency prices on that exchange are quoted in.
# London quotes in pence ("GBp"), not pounds.
_SUFFIX_CURRENCY = {
    "NS": "INR", "BO": "INR", "TO": "CAD", "V": "CAD", "L": "GBp", "HK": "HKD", "T": "JPY",
    "AX": "AUD", "PA": "EUR", "DE": "EUR", "AS": "EUR", "MI": "EUR", "SS": "CNY", "SZ": "CNY", "KS": "KRW",
}
# Minor units quoted by some exchanges: (major currency, minor units per major unit).
MINOR_UNITS = {"GBp": ("GBP", 100)}


def native_currency(symbol: str) -> str | None:
    """
    The currency `symbol` is priced in, or None when it isn't money (index points)
    or can't be known — callers must then show the number unconverted.
    """
    if symbol in _YAHOO_INDEX:
        return None
    if symbol.endswith("-USD"):
        return "USD"
    if _SHARE_CLASS_RE.match(symbol) or re.fullmatch(r"[A-Z][A-Z0-9]{0,5}", symbol):
        return "USD"  # US-listed equity / ETF, incl. share classes like BRK.B
    m = re.search(r"\.([A-Z]{1,2})$", symbol)
    return _SUFFIX_CURRENCY.get(m.group(1)) if m else None


def fx_pair(currency: str) -> str | None:
    """Yahoo's daily rate symbol for `currency` per 1 USD (None for USD itself)."""
    major = MINOR_UNITS.get(currency, (currency, 1))[0]
    return None if major == "USD" else f"USD{major}=X"
