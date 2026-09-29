"""
pipeline/scraper/india_rss.py
─────────────────────────────
Indian market news from publisher RSS feeds (Finviz covers US-listed stocks only).

Items become ordinary `articles` rows with market='india', so they flow through
the same body fetch → LLM extraction → verification → report → sync stages.
A failing feed is logged and skipped; the stage fails only if every feed fails.

    python -m pipeline.scraper.india_rss        # one pass, prints counts
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import httpx
from lxml import etree
from sqlalchemy.dialects.postgresql import insert as pg_insert

from pipeline.config import settings
from pipeline.db.local import LocalSession
from pipeline.db.models import Article
from pipeline.market_time import compute_trading_day
from pipeline.noise.tagger import tag_article
from pipeline.scraper.dedup import canonical_url, title_hash

log = logging.getLogger(__name__)

MARKET = "india"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140 Safari/537.36"
SOURCE_NAMES = {
    "economictimes.indiatimes.com": "Economic Times",
    "livemint.com": "Mint",
    "business-standard.com": "Business Standard",
    "moneycontrol.com": "Moneycontrol",
    "thehindubusinessline.com": "BusinessLine",
}


@dataclass(frozen=True)
class FeedItem:
    url: str
    headline: str
    source_name: str
    published_at: datetime | None


def _source_name(url: str) -> str:
    host = urlparse(url).hostname or ""
    host = host.removeprefix("www.")
    return SOURCE_NAMES.get(host, host)


def _published(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw.strip())
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def parse_feed(xml: bytes, feed_url: str) -> list[FeedItem]:
    """RSS 2.0 <item>s → FeedItems (items without a link or title are dropped)."""
    root = etree.fromstring(xml, parser=etree.XMLParser(recover=True, resolve_entities=False, no_network=True))
    if root is None:
        return []
    items = []
    for node in root.iter("item"):
        link = (node.findtext("link") or node.findtext("guid") or "").strip()
        headline = " ".join((node.findtext("title") or "").split())
        if not link.startswith(("http://", "https://")) or not headline:
            continue
        items.append(FeedItem(link, headline, _source_name(link) or _source_name(feed_url), _published(node.findtext("pubDate"))))
    return items


def fetch_items(feeds: list[str]) -> tuple[list[FeedItem], int]:
    """Fetch every feed. Returns (items, number of feeds that failed)."""
    items: list[FeedItem] = []
    failed = 0
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=15, follow_redirects=True) as client:
        for feed in feeds:
            try:
                resp = client.get(feed)
                resp.raise_for_status()
                parsed = parse_feed(resp.content, feed)
            except Exception as exc:  # noqa: BLE001 — network, HTTP or XML errors: skip this feed
                failed += 1
                log.warning("India feed failed: %s (%s)", feed, exc)
                continue
            log.debug("India feed %s: %d items", feed, len(parsed))
            items.extend(parsed)
    return items, failed


def _store(items: list[FeedItem], now: datetime) -> tuple[int, int]:
    """Upsert items as articles. Returns (new, updated)."""
    new = updated = 0
    with LocalSession() as session:
        for it in items:
            noise = tag_article(it.headline)
            stmt = pg_insert(Article).values(
                canonical_url=canonical_url(it.url),
                url=it.url,
                headline=it.headline,
                title_hash=title_hash(it.source_name, it.headline),
                source_name=it.source_name,
                published_at=it.published_at or now,
                first_seen_at=now,
                last_seen_at=now,
                seen_count=1,
                is_internal=False,
                noise_tags=noise,
                status="noise_tagged" if noise else "new",
                trading_day=compute_trading_day(it.published_at or now),
                market=MARKET,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["canonical_url"],
                set_={"last_seen_at": now, "seen_count": Article.seen_count + 1},
            ).returning(Article.seen_count)
            if session.execute(stmt).scalar_one() == 1:
                new += 1
            else:
                updated += 1
        session.commit()
    return new, updated


def scrape_india(feeds: list[str] | None = None) -> dict[str, int]:
    """One pass over the configured feeds. Raises only when every feed fails."""
    feeds = settings.india_feed_list if feeds is None else feeds
    if not feeds:
        return {"feeds": 0, "found": 0, "new": 0, "updated": 0, "failed_feeds": 0}
    now = datetime.now(UTC)
    items, failed = fetch_items(feeds)
    if failed == len(feeds):
        raise RuntimeError(f"all {failed} India feeds failed")

    cutoff = now - timedelta(hours=settings.india_max_age_hours)
    unique: dict[str, FeedItem] = {}
    for it in items:  # the Economic Times feeds overlap; keep one row per URL
        if it.published_at is None or it.published_at >= cutoff:
            unique.setdefault(canonical_url(it.url), it)
    new, updated = _store(list(unique.values()), now)
    log.info("India feeds: %d items (%d fresh), %d new, %d updated, %d feed(s) failed",
             len(items), len(unique), new, updated, failed)
    return {"feeds": len(feeds), "found": len(unique), "new": new, "updated": updated, "failed_feeds": failed}


if __name__ == "__main__":
    from pipeline.logging_setup import setup_logging

    setup_logging("pipeline.log")
    print(scrape_india())
