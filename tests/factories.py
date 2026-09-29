"""Helpers that insert realistic rows through the ORM."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from pipeline.db.models import Article, ArticleTicker, Extraction, PriceDaily, Ticker

NOW = datetime.now(UTC)


def add_article(session, *, id_hint: str = "1", status: str = "verified", tickers=("NVDA",), sector="Technology",
                trading_day: date | None = None, extraction: bool = True, body: str | None = "Body text.",
                published_at: datetime | None = None, sentiment: str = "bullish", event_type: str = "earnings",
                one_line: str | None = None, **fields) -> Article:
    for sym in tickers:
        if session.get(Ticker, sym) is None:
            session.add(Ticker(symbol=sym, sector=sector, last_seen_at=NOW))
    art = Article(
        canonical_url=f"https://example.com/story-{id_hint}",
        url=f"https://Example.com/Story-{id_hint}",
        headline=fields.pop("headline", f"Headline {id_hint}"),
        source_name="Reuters",
        published_at=published_at or NOW - timedelta(minutes=5),
        last_seen_at=NOW,
        status=status,
        trading_day=trading_day or date.today(),
        body=body,
        **fields,
    )
    session.add(art)
    session.flush()
    for sym in tickers:
        session.add(ArticleTicker(article_id=art.id, ticker=sym, pct_change=1.0))
    if extraction:
        session.add(Extraction(article_id=art.id, tickers=list(tickers), event_type=event_type, sentiment=sentiment,
                               key_facts=["fact"], numbers=[], one_line=one_line or f"Summary {id_hint}", evidence="quote",
                               model_used="test"))
    session.commit()
    return art


def add_prices(session, symbol: str, closes: list[float]) -> None:
    start = date.today() - timedelta(days=len(closes))
    for i, c in enumerate(closes):
        session.add(PriceDaily(ticker=symbol, date=start + timedelta(days=i), open=c, high=c, low=c, close=c, volume=100))
    session.commit()
