from datetime import UTC, datetime

from pipeline.extract.prompt import normalize_extraction
from pipeline.scraper.india_rss import parse_feed

FEED = b"""<?xml version="1.0"?><rss><channel>
<item><title> Sensex  falls 1,100 points </title><link>https://economictimes.indiatimes.com/markets/a.cms</link>
<pubDate>Mon, 28 Sep 2026 18:20:05 +0530</pubDate></item>
<item><title>No link</title></item>
<item><title>Rupee nears 96</title><guid>https://www.livemint.com/market/b</guid><pubDate>garbage</pubDate></item>
</channel></rss>"""


def test_parse_feed_items():
    items = parse_feed(FEED, "https://economictimes.indiatimes.com/rss")
    assert [i.headline for i in items] == ["Sensex falls 1,100 points", "Rupee nears 96"]
    assert items[0].source_name == "Economic Times" and items[1].source_name == "Mint"
    assert items[0].published_at == datetime(2026, 9, 28, 12, 50, 5, tzinfo=UTC)
    assert items[1].published_at is None and items[1].url == "https://www.livemint.com/market/b"


def test_parse_feed_tolerates_broken_xml():
    assert parse_feed(b"<rss><channel><item><title>x", "https://x.com/rss") == []


def test_extraction_accepts_indian_symbols_and_sector():
    data = normalize_extraction({"tickers": ["RELIANCE.NS", "M&M.NS", "MICROSOFT", "nvda"], "sector": "Banking", "one_line": "x"})
    assert data["tickers"] == ["RELIANCE.NS", "M&M.NS", "NVDA"]
    assert data["sector"] == "Financials"
    assert normalize_extraction({"sector": "Macro", "one_line": "x"})["sector"] is None
