"""
pipeline/db/models.py
─────────────────────
All SQLAlchemy ORM table definitions for the stock-news pipeline.

Local PostgreSQL holds the complete dataset (including article bodies,
raw evidence, etc.).  Neon holds only the public-safe subset.

Eight tables:
  1. articles
  2. article_tickers
  3. extractions
  4. tickers
  5. prices_daily
  6. scrape_runs
  7. reports
  8. sector_day_features   (schema-only; populated in a future milestone)
  9. story_clusters        (schema-only; deferred)
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    Column,
    Date,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    PrimaryKeyConstraint,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, relationship


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


# ---------------------------------------------------------------------------
# 1. articles
# ---------------------------------------------------------------------------

class Article(Base):
    """
    One row per unique news article (deduplicated by canonical_url).

    Status pipeline:
        new → noise_tagged → body_fetched → extracted → verified
    """
    __tablename__ = "articles"

    id: int = Column(BigInteger, primary_key=True, autoincrement=True)

    # Deduplication
    canonical_url: str = Column(Text, nullable=False, unique=True)
    headline: str = Column(Text, nullable=False)
    # sha256(source_name + normalize_whitespace(headline.lower()))
    # Index only — not UNIQUE; catches same story / URL variant from same outlet
    title_hash: str = Column(Text, nullable=True, index=True)
    source_name: str = Column(Text, nullable=True)

    # Timestamps
    published_at: datetime = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="Computed: scrape_time − age_string",
    )
    first_seen_at: datetime = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default="now()",
        comment="Set once at insert; never updated",
    )
    last_seen_at: datetime = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        comment="Bumped on every re-scrape",
    )
    seen_count: int = Column(Integer, nullable=False, default=1)

    # Source classification
    is_internal: bool = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="True = Finviz-hosted /news/... URL",
    )

    # Content
    body: str = Column(
        Text,
        nullable=True,
        comment="Full article body — never synced to Neon",
    )
    content_quality: str = Column(
        Text,
        nullable=True,
        comment="full | snippet | headline",
    )
    noise_tags: list[str] = Column(
        ARRAY(Text),
        nullable=True,
        server_default="{}",
        comment="e.g. {law_firm_loss, dividend_routine}",
    )

    # Status tracking
    status: str = Column(
        Text,
        nullable=False,
        default="new",
        comment="new|noise_tagged|body_fetched|extracted|verified",
    )

    # Trading day (4 PM ET boundary)
    trading_day: date = Column(
        Date,
        nullable=True,
        comment="US trading day this article belongs to",
    )

    # Relationships
    tickers_rel = relationship(
        "ArticleTicker",
        back_populates="article",
        cascade="all, delete-orphan",
    )
    extraction = relationship(
        "Extraction",
        back_populates="article",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_articles_status", "status"),
        Index("ix_articles_trading_day", "trading_day"),
        Index("ix_articles_published_at", "published_at"),
    )

    def __repr__(self) -> str:
        return f"<Article id={self.id} status={self.status!r} headline={self.headline[:60]!r}>"


# ---------------------------------------------------------------------------
# 2. article_tickers
# ---------------------------------------------------------------------------

class ArticleTicker(Base):
    """
    Many-to-many: one article can mention many tickers.
    Composite PK: (article_id, ticker).  Additive — never deleted.
    """
    __tablename__ = "article_tickers"

    article_id: int = Column(
        BigInteger,
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
    )
    ticker: str = Column(Text, nullable=False)
    # Regular session % change (null if not shown on Finviz row)
    pct_change: float = Column(Numeric(8, 4), nullable=True)
    # After-hours % change (null if not shown)
    pct_change_ah: float = Column(Numeric(8, 4), nullable=True)

    # Relationship back to article
    article = relationship("Article", back_populates="tickers_rel")

    __table_args__ = (
        PrimaryKeyConstraint("article_id", "ticker"),
        Index("ix_article_tickers_ticker", "ticker"),
    )

    def __repr__(self) -> str:
        return f"<ArticleTicker article_id={self.article_id} ticker={self.ticker!r}>"


# ---------------------------------------------------------------------------
# 3. extractions
# ---------------------------------------------------------------------------

class Extraction(Base):
    """
    LLM-extracted structured insight for one article.
    One-to-one with Article (UNIQUE on article_id).
    """
    __tablename__ = "extractions"

    id: int = Column(BigInteger, primary_key=True, autoincrement=True)
    article_id: int = Column(
        BigInteger,
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # LLM output fields (mirrors exact JSON keys returned by OmniRoute)
    tickers: list[str] = Column(
        ARRAY(Text),
        nullable=True,
        comment="LLM-confirmed tickers e.g. ['NVDA', 'AMD']",
    )
    event_type: str = Column(
        Text,
        nullable=True,
        comment="e.g. earnings, merger, macro, regulatory",
    )
    sentiment: str = Column(
        Text,
        nullable=True,
        comment="bullish | bearish | neutral",
    )
    # key_facts and evidence are NOT synced to Neon
    key_facts: list = Column(
        JSONB,
        nullable=True,
        comment="Array of fact strings — not synced to Neon",
    )
    numbers: list = Column(
        JSONB,
        nullable=True,
        comment="[{value, unit, context}] — numbers extracted from body",
    )
    one_line: str = Column(
        Text,
        nullable=True,
        comment="Public-safe one-sentence summary",
    )
    evidence: str = Column(
        Text,
        nullable=True,
        comment="Verbatim quote from body used for verification — not synced to Neon",
    )

    # Provenance
    model_used: str = Column(
        Text,
        nullable=True,
        comment="Which OmniRoute model actually responded",
    )
    created_at: datetime = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default="now()",
    )

    # Relationship
    article = relationship("Article", back_populates="extraction")

    def __repr__(self) -> str:
        return (
            f"<Extraction id={self.id} article_id={self.article_id} "
            f"event_type={self.event_type!r} sentiment={self.sentiment!r}>"
        )


# ---------------------------------------------------------------------------
# 4. tickers
# ---------------------------------------------------------------------------

class Ticker(Base):
    """
    Reference table for known tickers with company metadata.
    Populated / updated on each Finviz scrape.
    """
    __tablename__ = "tickers"

    symbol: str = Column(Text, primary_key=True)
    company_name: str = Column(
        Text,
        nullable=True,
        comment="From data-boxover-company attribute on Finviz",
    )
    finviz_industry: str = Column(
        Text,
        nullable=True,
        comment="Finviz industry label e.g. 'Semiconductors'",
    )
    sector: str = Column(
        Text,
        nullable=True,
        comment="GICS sector mapped via sector_map.py",
    )
    country: str = Column(
        Text,
        nullable=True,
        comment="From data-boxover-country attribute on Finviz",
    )
    last_seen_at: datetime = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_tickers_sector", "sector"),
    )

    def __repr__(self) -> str:
        return f"<Ticker symbol={self.symbol!r} sector={self.sector!r}>"


# ---------------------------------------------------------------------------
# 5. prices_daily
# ---------------------------------------------------------------------------

class PriceDaily(Base):
    """
    Daily OHLCV data fetched from Finnhub.
    Composite PK: (ticker, date).
    """
    __tablename__ = "prices_daily"

    ticker: str = Column(Text, nullable=False)
    date: date = Column(Date, nullable=False)
    open: float = Column(Numeric(12, 4), nullable=True)
    high: float = Column(Numeric(12, 4), nullable=True)
    low: float = Column(Numeric(12, 4), nullable=True)
    close: float = Column(Numeric(12, 4), nullable=True)
    volume: int = Column(BigInteger, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("ticker", "date"),
        Index("ix_prices_daily_ticker", "ticker"),
        Index("ix_prices_daily_date", "date"),
    )

    def __repr__(self) -> str:
        return f"<PriceDaily ticker={self.ticker!r} date={self.date} close={self.close}>"


# ---------------------------------------------------------------------------
# 6. scrape_runs
# ---------------------------------------------------------------------------

class ScrapeRun(Base):
    """
    Audit log for every Finviz scrape attempt.
    Opened at start of scrape, updated at end.
    """
    __tablename__ = "scrape_runs"

    id: int = Column(BigInteger, primary_key=True, autoincrement=True)
    started_at: datetime = Column(TIMESTAMP(timezone=True), nullable=False)
    finished_at: datetime = Column(TIMESTAMP(timezone=True), nullable=True)

    # Counts
    items_found: int = Column(Integer, nullable=True, comment="Total rows on page")
    items_new: int = Column(Integer, nullable=True, comment="Newly inserted")
    items_updated: int = Column(Integer, nullable=True, comment="last_seen_at bumped")
    error_count: int = Column(Integer, nullable=False, default=0)

    # Coverage
    oldest_article_age: str = Column(
        Text,
        nullable=True,
        comment="Raw age string of oldest row seen e.g. 'Sep-18'",
    )
    oldest_article_ts: datetime = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="Computed absolute timestamp of oldest article",
    )
    coverage_hours: float = Column(
        Numeric,
        nullable=True,
        comment="(scrape_time − oldest_article_ts) in hours",
    )

    # Per-domain stats
    per_domain_stats: dict = Column(
        JSONB,
        nullable=True,
        comment="{domain: {fetched, failed, quality}}",
    )

    # Status
    status: str = Column(
        Text,
        nullable=False,
        default="running",
        comment="running | done | failed",
    )

    __table_args__ = (
        Index("ix_scrape_runs_started_at", "started_at"),
        Index("ix_scrape_runs_status", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<ScrapeRun id={self.id} status={self.status!r} "
            f"items_new={self.items_new} started_at={self.started_at}>"
        )


# ---------------------------------------------------------------------------
# 7. reports
# ---------------------------------------------------------------------------

class Report(Base):
    """
    Daily market synthesis report generated by Claude.ai.
    One row per trading day.
    """
    __tablename__ = "reports"

    id: int = Column(BigInteger, primary_key=True, autoincrement=True)
    trading_day: date = Column(
        Date,
        nullable=False,
        unique=True,
        comment="One report per US trading day",
    )
    content: str = Column(
        Text,
        nullable=False,
        comment="Full Claude.ai response text",
    )
    article_ids: list[int] = Column(
        ARRAY(BigInteger),
        nullable=True,
        comment="Article IDs cited in this report",
    )
    created_at: datetime = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default="now()",
    )

    def __repr__(self) -> str:
        return f"<Report id={self.id} trading_day={self.trading_day}>"


# ---------------------------------------------------------------------------
# 8. sector_day_features  (schema-only — populated in a future milestone)
# ---------------------------------------------------------------------------

class SectorDayFeature(Base):
    """
    Aggregated features per sector per trading day.
    Schema created now; will be populated once extraction volume is sufficient
    to enable the readiness gate checks.
    """
    __tablename__ = "sector_day_features"

    sector: str = Column(Text, nullable=False)
    trading_day: date = Column(Date, nullable=False)
    article_count: int = Column(Integer, nullable=True)
    usable_count: int = Column(
        Integer,
        nullable=True,
        comment="Extracted + not noise",
    )

    __table_args__ = (
        PrimaryKeyConstraint("sector", "trading_day"),
    )

    def __repr__(self) -> str:
        return f"<SectorDayFeature sector={self.sector!r} trading_day={self.trading_day}>"


# ---------------------------------------------------------------------------
# 9. story_clusters  (deferred — schema only)
# ---------------------------------------------------------------------------

class StoryCluster(Base):
    """
    Future: group related articles about the same story.
    Schema created now; not populated until story-clustering is implemented.
    """
    __tablename__ = "story_clusters"

    id: int = Column(BigInteger, primary_key=True, autoincrement=True)
    created_at: datetime = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
        server_default="now()",
    )

    def __repr__(self) -> str:
        return f"<StoryCluster id={self.id}>"


# ---------------------------------------------------------------------------
# Exported symbols
# ---------------------------------------------------------------------------
__all__ = [
    "Base",
    "Article",
    "ArticleTicker",
    "Extraction",
    "Ticker",
    "PriceDaily",
    "ScrapeRun",
    "Report",
    "SectorDayFeature",
    "StoryCluster",
]
