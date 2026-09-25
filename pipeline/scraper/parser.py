"""
pipeline/scraper/parser.py
──────────────────────────
Parses raw Playwright page HTML into structured article rows using the
confirmed Finviz selectors from the implementation plan.

Selectors (locked):
  All news rows       table.styled-table-new tr.news_table-row
  Age text            first td.news_date-cell in row
  Headline anchor     a.nn-tab-link inside div.news-badges-container
  External link       has rel="nofollow" → href is full URL
  Internal link       no rel="nofollow"  → href starts with /news/
  Ticker anchors      a.fv-label.stock-news-label  (skip bare <span>)
  Ticker symbol       span.select-none.font-semibold inside ticker anchor
  % change            text node after <span> inside ticker anchor
  AH % change         text ends with " AH" — separate <a> for same ticker
  Source label        last span.news_date-cell inside div.news-badges-container
  +N More badge       span.fv-label with no <a> wrapper — SKIP

Age string formats:
  "X min"    → scrape_time − X minutes
  "X hour[s]"→ scrape_time − X hours
  "Sep-19"   → midnight ET of that date (year inferred from proximity)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytz
from bs4 import BeautifulSoup, Tag

from pipeline.scraper.dedup import canonical_url, title_hash
from pipeline.scraper.sector_map import get_sector

log = logging.getLogger(__name__)

ET = pytz.timezone("America/New_York")

# Params we do NOT want on Finviz internal links
_FINVIZ_BASE = "https://finviz.com"

# Month abbreviation → month number
_MONTH_ABBR = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

_AGE_MIN_RE  = re.compile(r"^(\d+)\s+min$", re.IGNORECASE)
_AGE_HOUR_RE = re.compile(r"^(\d+)\s+hours?$", re.IGNORECASE)
_AGE_DATE_RE = re.compile(r"^([A-Za-z]{3})-(\d{1,2})$")


@dataclass
class TickerData:
    symbol: str
    pct_change: float | None = None
    pct_change_ah: float | None = None
    company_name: str | None = None
    finviz_industry: str | None = None
    sector: str | None = None
    country: str | None = None


@dataclass
class ParsedArticle:
    raw_url: str
    canonical: str
    headline: str
    source_name: str
    hash: str
    published_at: datetime | None
    trading_day: "date | None"
    is_internal: bool
    tickers: list[TickerData] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Age → datetime
# ---------------------------------------------------------------------------

def parse_age(age_text: str, scrape_time: datetime) -> datetime | None:
    """Convert a Finviz age string into an absolute UTC datetime."""
    t = age_text.strip()

    m = _AGE_MIN_RE.match(t)
    if m:
        from datetime import timedelta
        return scrape_time - timedelta(minutes=int(m.group(1)))

    m = _AGE_HOUR_RE.match(t)
    if m:
        from datetime import timedelta
        return scrape_time - timedelta(hours=int(m.group(1)))

    m = _AGE_DATE_RE.match(t)
    if m:
        mon_str, day_str = m.group(1).lower(), int(m.group(2))
        month = _MONTH_ABBR.get(mon_str)
        if month is None:
            return None
        # Infer year: if month/day is in the future relative to scrape_time, use prior year
        now_et = scrape_time.astimezone(ET)
        year = now_et.year
        try:
            candidate = ET.localize(
                datetime(year, month, day_str, 0, 0, 0)
            )
        except Exception:
            return None
        # If candidate is more than 1 day in the future, roll back a year
        if (candidate - scrape_time).total_seconds() > 86400:
            candidate = ET.localize(datetime(year - 1, month, day_str, 0, 0, 0))
        return candidate.astimezone(timezone.utc)

    log.debug("Unknown age format: %r", age_text)
    return None


def compute_trading_day(published_at: datetime | None, scrape_time: datetime) -> "date | None":
    """
    US trading day boundary: 4 PM ET.
    Articles published before 4 PM ET belong to that calendar day;
    articles published at/after 4 PM ET belong to the NEXT trading day.
    (Weekend articles roll to Monday — simplified here to just use date.)
    """
    if published_at is None:
        return None
    from datetime import date, timedelta
    et_time = published_at.astimezone(ET)
    if et_time.hour >= 16:
        return (et_time + timedelta(days=1)).date()
    return et_time.date()


# ---------------------------------------------------------------------------
# % change text → float
# ---------------------------------------------------------------------------

_PCT_RE = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*%")


def _parse_pct(text: str) -> float | None:
    """Extract a percentage value from text like '+1.23%' or '-0.45% AH'."""
    m = _PCT_RE.search(text)
    if m:
        return float(m.group(1))
    return None


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse_finviz_html(html: str, scrape_time: datetime) -> list[ParsedArticle]:
    """
    Parse the full Finviz news page HTML into a list of ParsedArticle objects.

    Args:
        html:        Raw HTML string from Playwright.
        scrape_time: UTC datetime of when the page was fetched.

    Returns:
        List of ParsedArticle objects (one per unique news row).
    """
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("table.styled-table-new tr.news_table-row")
    log.info("Parser found %d news rows", len(rows))

    articles: list[ParsedArticle] = []

    for row in rows:
        try:
            article = _parse_row(row, scrape_time)
            if article is not None:
                articles.append(article)
        except Exception as exc:
            log.warning("Failed to parse row: %s", exc, exc_info=True)

    log.info("Parser produced %d articles", len(articles))
    return articles


def _parse_row(row: Tag, scrape_time: datetime) -> ParsedArticle | None:
    """Parse a single news row <tr> into a ParsedArticle."""

    # ── Age ──────────────────────────────────────────────────────────────
    age_cell = row.select_one("td.news_date-cell")
    age_text = age_cell.get_text(strip=True) if age_cell else ""
    published_at = parse_age(age_text, scrape_time)

    # ── Badges container ─────────────────────────────────────────────────
    badges = row.select_one("div.news-badges-container")
    if badges is None:
        return None

    # ── Headline anchor ───────────────────────────────────────────────────
    anchor = badges.select_one("a.nn-tab-link")
    if anchor is None:
        return None

    headline = anchor.get_text(strip=True)
    if not headline:
        return None

    href = anchor.get("href", "")
    rel  = anchor.get("rel", [])
    if isinstance(rel, str):
        rel = [rel]

    # External = has rel="nofollow"; Internal = starts with /news/
    is_external = "nofollow" in rel
    if is_external:
        raw_url = href
    else:
        # Internal Finviz URL — prepend base
        if href.startswith("/"):
            raw_url = _FINVIZ_BASE + href
        else:
            raw_url = href

    if not raw_url:
        return None

    is_internal = not is_external
    can_url = canonical_url(raw_url)

    # ── Source label ──────────────────────────────────────────────────────
    # Last span.news_date-cell inside badges container
    source_spans = badges.select("span.news_date-cell")
    source_name = source_spans[-1].get_text(strip=True) if source_spans else ""

    t_hash = title_hash(source_name, headline)
    trading_day = compute_trading_day(published_at, scrape_time)

    # ── Ticker anchors ────────────────────────────────────────────────────
    # Only <a> tags with class "fv-label stock-news-label"; skip bare <span>
    ticker_anchors = row.select("a.fv-label.stock-news-label")

    # Accumulate per-symbol so regular + AH can be merged into one TickerData
    ticker_map: dict[str, TickerData] = {}

    for ta in ticker_anchors:
        sym_span = ta.select_one("span.select-none.font-semibold")
        if sym_span is None:
            continue
        symbol = sym_span.get_text(strip=True).upper()
        if not symbol:
            continue

        # Full text of the anchor (includes symbol + pct text)
        full_text = ta.get_text(strip=True)
        # Remove the symbol itself to isolate the pct change text
        pct_text = full_text.replace(symbol, "", 1).strip()
        pct_val = _parse_pct(pct_text)

        is_ah = pct_text.upper().endswith("AH") or " AH" in pct_text.upper()

        # Ticker metadata from data attributes (best-effort)
        company_name    = ta.get("data-boxover-company") or None
        finviz_industry = ta.get("data-boxover-industry") or None
        country         = ta.get("data-boxover-country") or None
        sector          = get_sector(finviz_industry) if finviz_industry else None

        if symbol not in ticker_map:
            ticker_map[symbol] = TickerData(
                symbol=symbol,
                company_name=company_name,
                finviz_industry=finviz_industry,
                sector=sector,
                country=country,
            )

        td = ticker_map[symbol]
        if is_ah:
            td.pct_change_ah = pct_val
        else:
            td.pct_change = pct_val

        # Update metadata if we got it this pass
        if company_name and not td.company_name:
            td.company_name = company_name
        if finviz_industry and not td.finviz_industry:
            td.finviz_industry = finviz_industry
            td.sector = get_sector(finviz_industry)
        if country and not td.country:
            td.country = country

    return ParsedArticle(
        raw_url=raw_url,
        canonical=can_url,
        headline=headline,
        source_name=source_name,
        hash=t_hash,
        published_at=published_at,
        trading_day=trading_day,
        is_internal=is_internal,
        tickers=list(ticker_map.values()),
    )
