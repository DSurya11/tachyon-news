from datetime import UTC, date, datetime

from pipeline.market_time import compute_trading_day, current_trading_day
from pipeline.scraper.dedup import canonical_url, title_hash
from pipeline.scraper.parser import parse_age, parse_finviz_html
from tests.fixtures import FINVIZ_HTML

# Wednesday 2026-09-23 18:00 UTC = 14:00 ET
SCRAPE_TIME = datetime(2026, 9, 23, 18, 0, tzinfo=UTC)


def test_parses_rows_and_skips_malformed():
    arts = parse_finviz_html(FINVIZ_HTML, SCRAPE_TIME)
    assert [a.headline[:6] for a in arts] == ["Nvidia", "Acme D", "Fed ho"]


def test_external_row_fields():
    art = parse_finviz_html(FINVIZ_HTML, SCRAPE_TIME)[0]
    assert art.source_name == "Reuters"
    assert not art.is_internal
    # original URL keeps its case; canonical is normalised for dedup
    assert art.raw_url == "https://www.Example.com/Markets/Nvidia-Beats?utm_source=finviz#top"
    assert art.canonical == "https://www.example.com/markets/nvidia-beats"
    assert art.published_at == datetime(2026, 9, 23, 17, 55, tzinfo=UTC)
    assert art.trading_day == date(2026, 9, 23)


def test_regular_and_after_hours_change_merge_into_one_ticker():
    (nvda,) = parse_finviz_html(FINVIZ_HTML, SCRAPE_TIME)[0].tickers
    assert (nvda.symbol, nvda.pct_change, nvda.pct_change_ah) == ("NVDA", 2.5, 0.4)
    assert (nvda.company_name, nvda.sector, nvda.country) == ("NVIDIA Corp", "Technology", "USA")


def test_internal_finviz_link_gets_base_url():
    art = parse_finviz_html(FINVIZ_HTML, SCRAPE_TIME)[1]
    assert art.is_internal
    assert art.raw_url == "https://finviz.com/news/123/Acme-Declares-Quarterly-Dividend"
    assert art.tickers[0].sector == "Financials"


def test_parse_age_formats():
    assert parse_age("12 min", SCRAPE_TIME) == datetime(2026, 9, 23, 17, 48, tzinfo=UTC)
    assert parse_age("1 hour", SCRAPE_TIME) == datetime(2026, 9, 23, 17, 0, tzinfo=UTC)
    # date-only ages are midnight ET
    assert parse_age("Sep-19", SCRAPE_TIME) == datetime(2026, 9, 19, 4, 0, tzinfo=UTC)
    # a date "in the future" belongs to last year
    assert parse_age("Dec-30", SCRAPE_TIME).year == 2025
    assert parse_age("Feb-30", SCRAPE_TIME) is None
    assert parse_age("yesterday", SCRAPE_TIME) is None


def test_trading_day_rolls_after_close_and_over_weekends():
    et_close = datetime(2026, 9, 25, 20, 0, tzinfo=UTC)  # Fri 16:00 ET
    assert compute_trading_day(datetime(2026, 9, 25, 19, 59, tzinfo=UTC)) == date(2026, 9, 25)
    assert compute_trading_day(et_close) == date(2026, 9, 28)  # → Monday
    assert compute_trading_day(datetime(2026, 9, 26, 15, 0, tzinfo=UTC)) == date(2026, 9, 28)  # Sat
    assert compute_trading_day(datetime(2026, 9, 27, 15, 0, tzinfo=UTC)) == date(2026, 9, 28)  # Sun
    assert compute_trading_day(datetime(2026, 9, 23, 22, 0, tzinfo=UTC)) == date(2026, 9, 24)
    assert compute_trading_day(None) is None
    assert current_trading_day(et_close) == date(2026, 9, 28)


def test_canonical_url_strips_tracking_and_fragment():
    assert canonical_url("https://Reuters.com/a/b/?utm_source=x&id=2&fbclid=z#frag") == "https://reuters.com/a/b?id=2"
    assert canonical_url("https://example.com") == "https://example.com/"


def test_title_hash_ignores_case_and_whitespace():
    assert title_hash("Reuters", "Fed  Holds Rates") == title_hash("Reuters", "fed holds rates")
    assert title_hash("Reuters", "x") != title_hash("AP", "x")
