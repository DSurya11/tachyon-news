"""
pipeline/scraper/finviz.py
──────────────────────────
Playwright headless scraper for https://finviz.com/news?v=3

Scrapes all news rows, parses them, runs the noise tagger,
then upserts into local Postgres:
  - articles          (canonical_url ON CONFLICT DO UPDATE)
  - article_tickers   (article_id, ticker ON CONFLICT DO UPDATE)
  - tickers           (symbol ON CONFLICT DO UPDATE)
  - scrape_runs       (opened at start, closed at finish)

Polite 2-second delay before any follow-up navigations (currently only
one page is scraped, but the delay is wired for future use).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from playwright.async_api import Page, async_playwright
from playwright.async_api import TimeoutError as PWTimeout
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from pipeline.db.local import LocalSession
from pipeline.db.models import Article, ArticleTicker, ScrapeRun, Ticker
from pipeline.noise.tagger import tag_article
from pipeline.scraper.parser import ParsedArticle, parse_finviz_html

log = logging.getLogger(__name__)

FINVIZ_URL = "https://finviz.com/news?v=3"
POLITE_DELAY_S = 2  # seconds between navigations
NEWS_ROW_SELECTOR = "table.styled-table-new tr.news_table-row"


# ---------------------------------------------------------------------------
# DB upsert helpers
# ---------------------------------------------------------------------------

def _upsert_scrape_run(session, started_at: datetime) -> ScrapeRun:
    run = ScrapeRun(started_at=started_at, status="running")
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def _upsert_tickers(session, articles: list[ParsedArticle]) -> None:
    """Insert or update ticker metadata rows using ON CONFLICT DO UPDATE."""
    # Deduplicate: last-write-wins per symbol across all articles
    ticker_map: dict[str, dict] = {}
    now = datetime.now(UTC)
    for art in articles:
        for td in art.tickers:
            existing = ticker_map.get(td.symbol, {})
            ticker_map[td.symbol] = {
                "symbol": td.symbol,
                "company_name": td.company_name or existing.get("company_name"),
                "finviz_industry": td.finviz_industry or existing.get("finviz_industry"),
                "sector": td.sector or existing.get("sector"),
                "country": td.country or existing.get("country"),
                "last_seen_at": now,
            }

    if not ticker_map:
        return

    stmt = pg_insert(Ticker).values(list(ticker_map.values()))
    stmt = stmt.on_conflict_do_update(
        index_elements=["symbol"],
        set_={
            "last_seen_at": stmt.excluded.last_seen_at,
            # Never overwrite known metadata with NULL from a sparse row
            "company_name": func.coalesce(stmt.excluded.company_name, Ticker.company_name),
            "finviz_industry": func.coalesce(stmt.excluded.finviz_industry, Ticker.finviz_industry),
            "sector": func.coalesce(stmt.excluded.sector, Ticker.sector),
            "country": func.coalesce(stmt.excluded.country, Ticker.country),
        },
    )
    session.execute(stmt)



def _upsert_articles(
    session,
    articles: list[ParsedArticle],
    scrape_time: datetime,
) -> tuple[int, int]:
    """
    Upsert articles and their ticker associations.
    Returns (items_new, items_updated).

    Uses INSERT … ON CONFLICT DO UPDATE for both tables to avoid
    duplicate-key errors when the same canonical URL appears multiple
    times in one scrape batch or was already in the DB.
    """
    items_new = 0
    items_updated = 0

    for art in articles:
        noise_tags = tag_article(art.headline)
        status = "noise_tagged" if noise_tags else "new"

        # ── Article upsert ───────────────────────────────────────────────
        art_stmt = pg_insert(Article).values(
            canonical_url=art.canonical,
            url=art.raw_url,
            headline=art.headline,
            title_hash=art.hash,
            source_name=art.source_name,
            published_at=art.published_at,
            first_seen_at=scrape_time,
            last_seen_at=scrape_time,
            seen_count=1,
            is_internal=art.is_internal,
            noise_tags=noise_tags,
            status=status,
            trading_day=art.trading_day,
        )
        art_stmt = art_stmt.on_conflict_do_update(
            index_elements=["canonical_url"],
            set_={
                "last_seen_at": scrape_time,
                "seen_count": Article.seen_count + 1,
                # Backfill the original URL for rows scraped before it was stored
                "url": func.coalesce(Article.url, art_stmt.excluded.url),
            },
        ).returning(Article.id, Article.seen_count)

        article_id, seen_count = session.execute(art_stmt).one()

        if seen_count == 1:
            items_new += 1
        else:
            items_updated += 1
            if noise_tags:
                existing = session.get(Article, article_id)
                if existing:
                    existing.noise_tags = sorted(set(existing.noise_tags or []) | set(noise_tags))

        # ── ArticleTicker upsert ─────────────────────────────────────────
        for td in art.tickers:
            at_stmt = pg_insert(ArticleTicker).values(
                article_id=article_id,
                ticker=td.symbol,
                pct_change=td.pct_change,
                pct_change_ah=td.pct_change_ah,
            )
            at_stmt = at_stmt.on_conflict_do_update(
                index_elements=["article_id", "ticker"],
                set_={
                    "pct_change":    at_stmt.excluded.pct_change,
                    "pct_change_ah": at_stmt.excluded.pct_change_ah,
                },
            )
            session.execute(at_stmt)

    return items_new, items_updated


# ---------------------------------------------------------------------------
# Playwright fetch
# ---------------------------------------------------------------------------

async def _fetch_page_html(url: str) -> str:
    """Launch headless Chromium, navigate to url, return full page HTML."""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )
        page: Page = await context.new_page()
        log.info("Navigating to %s", url)

        # Finviz never reaches "networkidle" (ads, live quotes), so wait for the
        # DOM and then for the news table itself.
        await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        try:
            await page.wait_for_selector(NEWS_ROW_SELECTOR, timeout=30_000)
        except PWTimeout:
            log.warning("News rows selector not found within timeout — proceeding anyway")

        # Polite delay before any follow-up navigations
        await asyncio.sleep(POLITE_DELAY_S)

        try:
            return await page.content()
        finally:
            await browser.close()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def run_scraper() -> ScrapeRun:
    """
    Full scrape: fetch → parse → noise-tag → upsert.
    Returns the completed ScrapeRun ORM object.
    """
    scrape_time = datetime.now(UTC)

    with LocalSession() as session:
        run = _upsert_scrape_run(session, scrape_time)
        run_id = run.id
        log.info("ScrapeRun #%d started", run_id)

    try:
        html = await _fetch_page_html(FINVIZ_URL)
        articles = parse_finviz_html(html, scrape_time)

        # Determine oldest article for coverage stats
        oldest_ts = min((a.published_at for a in articles if a.published_at), default=None)

        coverage_hours = None
        if oldest_ts is not None:
            coverage_hours = (scrape_time - oldest_ts).total_seconds() / 3600

        if not articles:
            raise RuntimeError("Finviz page parsed to 0 articles — selectors may have changed")

        with LocalSession() as session:
            run = session.get(ScrapeRun, run_id)

            _upsert_tickers(session, articles)
            items_new, items_updated = _upsert_articles(session, articles, scrape_time)

            # Close the scrape run
            run.finished_at = datetime.now(UTC)
            run.items_found = len(articles)
            run.items_new = items_new
            run.items_updated = items_updated
            run.oldest_article_ts = oldest_ts
            run.coverage_hours = coverage_hours
            run.status = "done"
            session.commit()
            session.refresh(run)

        log.info(
            "Scrape done: found=%d new=%d updated=%d coverage=%.1fh",
            len(articles), items_new, items_updated, coverage_hours or 0,
        )
        return run

    except Exception as exc:
        log.error("Scraper failed: %s", exc)  # traceback is logged by the orchestrator
        with LocalSession() as session:
            run = session.get(ScrapeRun, run_id)
            run.finished_at = datetime.now(UTC)
            run.status = "failed"
            run.error_count = 1
            session.commit()
        raise


def scrape() -> ScrapeRun:
    """Synchronous wrapper — called by the pipeline orchestrator."""
    return asyncio.run(run_scraper())
