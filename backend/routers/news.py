"""
News, sectors and the range summary.

Every data endpoint takes the same time window: `since` / `until` (ISO datetimes), or the
shorthands `hours` / `days` (the window then ends now). No window = all time. The dashboard's
range picker ("Last 24 hours", "30 days", "All time", custom dates) maps onto these.

Lists are paged server-side and filtered server-side (`/news`), and aggregates are computed
server-side (`/summary`), so the dashboard never downloads a whole range — the data grows
indefinitely, a browser shouldn't have to.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from cachetools import TTLCache
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import any_, exists, func, or_, select
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.reaction import reaction
from pipeline.db.models import Article, ArticleTicker, Extraction, Report, Ticker
from pipeline.db.queries import (
    MACRO_SECTOR,
    article_tickers,
    invalid_symbols,
    primary_sector,
    sector_lookup,
    sectors_for,
)
from pipeline.market_time import ET

router = APIRouter(tags=["news"])

DEFAULT_STATUSES = "verified,extracted"
REPORTED = ("verified", "extracted")
MARKETS = ("global", "india")
KNOWN_STATUSES = {"new", "noise_tagged", "body_fetched", "extracted", "verified", "extraction_failed"}
SENTIMENTS = {"bullish", "neutral", "bearish"}
MAX_DAYS = 3650
MAX_IDS = 500
MARKET_PARAM = Query(None, pattern="^(global|india)$", description="global (Finviz) or india (Indian feeds)")

_summary_cache: TTLCache = TTLCache(maxsize=256, ttl=60)


# ─── Time window ────────────────────────────────────────────────────────────────

def _aware(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=UTC) if dt is not None and dt.tzinfo is None else dt


def resolve_window(since: datetime | None, until: datetime | None, days: int | None, hours: int | None
                   ) -> tuple[datetime | None, datetime | None]:
    """(start, end) of the requested window; None = open-ended. `since` wins over hours/days."""
    since, until = _aware(since), _aware(until)
    if since is None and (hours or days):
        since = datetime.now(UTC) - (timedelta(hours=hours) if hours else timedelta(days=days or 0))
    if since and until and since > until:
        raise HTTPException(status_code=422, detail="`since` is after `until`")
    return since, until


def _in_window(stmt, since: datetime | None, until: datetime | None):
    if since is not None:
        stmt = stmt.where(Article.published_at >= since)
    if until is not None:
        stmt = stmt.where(Article.published_at < until)
    return stmt


def _window_params(
    since: datetime | None = Query(None, description="Window start (ISO datetime)"),
    until: datetime | None = Query(None, description="Window end (ISO datetime, exclusive)"),
    days: int | None = Query(None, ge=1, le=MAX_DAYS, description="Shorthand: the last N days"),
    hours: int | None = Query(None, ge=1, le=MAX_DAYS * 24, description="Shorthand: the last N hours"),
) -> tuple[datetime | None, datetime | None]:
    return resolve_window(since, until, days, hours)


# ─── Filters and shapes ─────────────────────────────────────────────────────────

def _parse_statuses(raw: str | None) -> list[str]:
    statuses = [s.strip() for s in (raw or "").split(",") if s.strip()]
    unknown = set(statuses) - KNOWN_STATUSES
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown status: {', '.join(sorted(unknown))}")
    return statuses


def _parse_ids(raw: str | None) -> list[int] | None:
    if not raw:
        return None
    try:
        ids = [int(x) for x in raw.split(",") if x.strip()]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="ids must be comma-separated integers") from exc
    if len(ids) > MAX_IDS:
        raise HTTPException(status_code=422, detail=f"At most {MAX_IDS} ids")
    return ids


def _sector_filter(sector: str):
    by_finviz = exists().where(
        ArticleTicker.article_id == Article.id,
        Ticker.symbol == ArticleTicker.ticker,
        Ticker.sector == sector,
    )
    by_llm = exists().where(Ticker.symbol == any_(Extraction.tickers), Ticker.sector == sector)
    return or_(by_finviz, by_llm, Extraction.sector == sector)


def top_picks_by_article(db: Session, since: date | None = None) -> dict[int, dict]:
    """
    Article id → {rank, why, trading_day} from the daily reports' "top picks" (all reports, or
    those from `since` on). When a story was picked on several days, the latest report wins.
    """
    stmt = select(Report.trading_day, Report.top_picks)
    if since is not None:
        stmt = stmt.where(Report.trading_day >= since)
    picks: dict[int, dict] = {}
    for day, items in db.execute(stmt.order_by(Report.trading_day)).all():
        for p in items or []:
            if isinstance(p, dict) and isinstance(p.get("id"), int):
                picks[p["id"]] = {"rank": p.get("rank"), "why": p.get("why") or "", "trading_day": day}
    return picks


def pick_ids_for_window(db: Session, since: datetime | None, until: datetime | None) -> set[int]:
    """
    The top picks a time range shows: those of every daily brief whose trading day falls in it.
    Picks belong to a brief, not to a publish time, so a range too short to hold a brief
    ("last hour", a weekend) shows the latest brief's picks instead of none.
    """
    first = since.astimezone(ET).date() if since else None
    last = (until or datetime.now(UTC)).astimezone(ET).date()
    stmt = select(Report.top_picks).where(Report.trading_day <= last)
    rows = db.execute(stmt.where(Report.trading_day >= first) if first else stmt).scalars().all()
    if not rows:
        rows = db.execute(stmt.order_by(Report.trading_day.desc()).limit(1)).scalars().all()
    return {p["id"] for items in rows for p in items or [] if isinstance(p, dict) and isinstance(p.get("id"), int)}


def _article_dict(a: Article, ext: Extraction | None, tickers: list[str], sector_of: dict[str, str],
                  picks: dict[int, dict] | None = None) -> dict:
    llm_sector = ext.sector if ext else None
    return {
        "id": a.id,
        "headline": a.headline,
        "source_name": a.source_name,
        "url": a.url or a.canonical_url,
        "canonical_url": a.canonical_url,
        "published_at": a.published_at,
        "trading_day": a.trading_day,
        "market": a.market,
        "status": a.status,
        "verified": a.status == "verified",
        "noise_tags": a.noise_tags or [],
        "event_type": ext.event_type if ext else None,
        "sentiment": ext.sentiment if ext else None,
        "one_line": ext.one_line if ext else None,
        "tickers": tickers,
        "sector": primary_sector(tickers, sector_of, llm_sector),
        "sectors": sectors_for(tickers, sector_of, llm_sector),
        "top_pick": (picks or {}).get(a.id),
    }


# ─── /news ──────────────────────────────────────────────────────────────────────

@router.get("/news")
def get_news(
    window: tuple = Depends(_window_params),
    sector: str | None = Query(None, description=f"GICS sector, or '{MACRO_SECTOR}'"),
    ticker: str | None = None,
    trading_day: date | None = None,
    q: str | None = Query(None, max_length=100, description="Case-insensitive search: headline, summary, source"),
    market: str | None = MARKET_PARAM,
    status: str | None = Query(DEFAULT_STATUSES, description="Comma-separated statuses"),
    sentiment: str | None = Query(None, description="Comma-separated: bullish, neutral, bearish"),
    event: str | None = Query(None, max_length=20, description="Event type, e.g. earnings"),
    verified_only: bool = Query(False, description="Only stories whose quote and numbers matched the source"),
    picks: bool = Query(False, description="Only the daily briefs' top picks, most recent pick day first, by rank"),
    ids: str | None = Query(None, description=f"Comma-separated article ids (max {MAX_IDS}); ignores the time window"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Paginated news, newest first (or by pick for `picks`), with the total for the filters."""
    since, until = window
    id_list = _parse_ids(ids)
    stmt = select(Article, Extraction).outerjoin(Extraction, Article.id == Extraction.article_id)

    statuses = _parse_statuses(status)
    if statuses:
        stmt = stmt.where(Article.status.in_(statuses))
    # Fetching by id (a brief's sources) ignores the window: citations must resolve whatever the range.
    # So do picks: they're the picks of the briefs in the range, whenever those stories came out.
    if id_list is not None:
        stmt = stmt.where(Article.id.in_(id_list))
    elif picks:
        stmt = stmt.where(Article.id.in_(pick_ids_for_window(db, since, until)))
    else:
        stmt = _in_window(stmt, since, until)
    if market:
        stmt = stmt.where(Article.market == market)
    if trading_day:
        stmt = stmt.where(Article.trading_day == trading_day)
    if q:
        needle = f"%{q.replace('%', '').replace('_', '')}%"
        stmt = stmt.where(or_(Article.headline.ilike(needle), Extraction.one_line.ilike(needle), Article.source_name.ilike(needle)))
    if sentiment:
        wanted = {s.strip() for s in sentiment.split(",") if s.strip()}
        if wanted - SENTIMENTS:
            raise HTTPException(status_code=422, detail=f"Unknown sentiment: {', '.join(sorted(wanted - SENTIMENTS))}")
        stmt = stmt.where(Extraction.sentiment.in_(wanted))
    if event:
        stmt = stmt.where(Extraction.event_type == event)
    if verified_only:
        stmt = stmt.where(Article.status == "verified")
    if ticker:
        sym = ticker.strip().upper()
        stmt = stmt.where(
            or_(
                exists().where(ArticleTicker.article_id == Article.id, ArticleTicker.ticker == sym),
                sym == any_(Extraction.tickers),
            )
        )
    if sector and sector != MACRO_SECTOR:
        stmt = stmt.where(_sector_filter(sector))

    pick_map = top_picks_by_article(db)

    offset = (page - 1) * limit
    # Picks sort by pick day and rank, and the macro bucket is defined by the *absence* of a
    # sector — both are resolved in Python over the (small) filtered set.
    in_python = picks or sector == MACRO_SECTOR
    if in_python:
        rows = db.execute(stmt.order_by(Article.published_at.desc().nulls_last(), Article.id.desc()).limit(5000)).all()
    else:
        total = db.execute(stmt.with_only_columns(func.count()).order_by(None)).scalar_one()
        rows = db.execute(
            stmt.order_by(Article.published_at.desc().nulls_last(), Article.id.desc()).offset(offset).limit(limit + 1)
        ).all()

    tickers_by_article = article_tickers(db, [a.id for a, _ in rows], {a.id: (e.tickers if e else []) for a, e in rows})
    sector_of = sector_lookup(db, {t for ts in tickers_by_article.values() for t in ts})
    articles = [_article_dict(a, e, tickers_by_article[a.id], sector_of, pick_map) for a, e in rows]

    if in_python:
        if sector == MACRO_SECTOR:
            articles = [a for a in articles if a["sectors"] == [MACRO_SECTOR]]
        if picks:
            articles.sort(key=lambda a: (-a["top_pick"]["trading_day"].toordinal(), a["top_pick"]["rank"] or 999))
        total = len(articles)
        articles = articles[offset : offset + limit + 1]

    return {
        "page": page,
        "limit": limit,
        "total": total,
        "has_more": len(articles) > limit,
        "articles": articles[:limit],
    }


@router.get("/news/{article_id}")
def get_article(article_id: int, db: Session = Depends(get_db)):
    """One article with its full extraction."""
    row = db.execute(
        select(Article, Extraction).outerjoin(Extraction, Article.id == Extraction.article_id).where(Article.id == article_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Article not found")
    article, ext = row
    tickers = article_tickers(db, [article.id], {article.id: ext.tickers if ext else []})[article.id]
    data = _article_dict(article, ext, tickers, sector_lookup(db, tickers), top_picks_by_article(db))
    data["extraction"] = (
        {
            "event_type": ext.event_type,
            "sentiment": ext.sentiment,
            "tickers": ext.tickers,
            "key_facts": ext.key_facts,
            "numbers": ext.numbers,
            "one_line": ext.one_line,
            "evidence": ext.evidence,
        }
        if ext
        else None
    )
    return data


_reaction_cache: TTLCache = TTLCache(maxsize=512, ttl=120)


@router.get("/news/{article_id}/reaction")
def get_reaction(article_id: int, db: Session = Depends(get_db)):
    """
    The priced-in meter: how far each of the story's stocks has moved since the headline beyond
    the market, and what similar stories were followed by (backend/reaction.py).
    """
    if article_id in _reaction_cache:
        return _reaction_cache[article_id]
    row = db.execute(
        select(Article.id, Article.published_at, Extraction.event_type, Extraction.sentiment, Extraction.tickers)
        .outerjoin(Extraction, Article.id == Extraction.article_id).where(Article.id == article_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Article not found")
    tickers = article_tickers(db, [row.id], {row.id: row.tickers or []})[row.id]
    result = reaction(db, row.id, row.published_at, tickers, row.event_type, row.sentiment)
    _reaction_cache[article_id] = result
    return result


# ─── Aggregates ─────────────────────────────────────────────────────────────────

def _window_rows(db: Session, since, until, market):
    """(id, published_at, status, sentiment, llm tickers, llm sector) for reported stories in the window."""
    stmt = _in_window(
        select(Article.id, Article.published_at, Article.status, Extraction.sentiment, Extraction.tickers, Extraction.sector)
        .join(Extraction, Extraction.article_id == Article.id)
        .where(Article.status.in_(REPORTED)),
        since, until,
    )
    return db.execute(stmt.where(Article.market == market) if market else stmt).all()


def _window_finviz_tickers(db: Session, since, until, market) -> dict[int, set[str]]:
    """Finviz-attached tickers per story in the window (joined, not an IN list: windows can be huge)."""
    stmt = _in_window(
        select(ArticleTicker.article_id, ArticleTicker.ticker)
        .join(Article, Article.id == ArticleTicker.article_id)
        .where(Article.status.in_(REPORTED)),
        since, until,
    )
    out: dict[int, set[str]] = defaultdict(set)
    for aid, sym in db.execute(stmt.where(Article.market == market) if market else stmt):
        out[aid].add(sym)
    return out


def _tally() -> dict:
    return {"count": 0, "bullish": 0, "neutral": 0, "bearish": 0, "verified": 0}


def _add(t: dict, sentiment: str | None, verified: bool) -> None:
    t["count"] += 1
    t[sentiment if sentiment in ("bullish", "bearish") else "neutral"] += 1
    t["verified"] += int(verified)


STEPS = {"5min": timedelta(minutes=5), "15min": timedelta(minutes=15), "hour": timedelta(hours=1),
         "day": timedelta(days=1), "week": timedelta(weeks=1)}


def _timeline_unit(start: datetime, end: datetime) -> str:
    """Bar size for a span: about 12–100 bars whatever the range (1 hour → 5-minute bars)."""
    span = end - start - timedelta(minutes=1)  # "last 12 hours" ends a moment after it was asked for
    if span <= timedelta(hours=2):
        return "5min"
    if span <= timedelta(hours=12):
        return "15min"
    return "hour" if span <= timedelta(hours=72) else "day" if span <= timedelta(days=400) else "week"


def _bucket_start(dt: datetime, unit: str) -> datetime:
    dt = dt.astimezone(UTC)
    if unit in ("5min", "15min"):
        size = 5 if unit == "5min" else 15
        return dt.replace(minute=dt.minute - dt.minute % size, second=0, microsecond=0)
    if unit == "hour":
        return dt.replace(minute=0, second=0, microsecond=0)
    day = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return day if unit == "day" else day - timedelta(days=day.weekday())


def _not_before_first_story(db: Session, since: datetime | None) -> datetime | None:
    """A year's chart of a week-old database starts where the stories do, not with 358 empty days."""
    first = db.scalar(select(func.min(Article.published_at)))
    return max(since, first) if since and first else since


def _timeline(rows, since, until) -> dict:
    now = datetime.now(UTC)
    times = [r.published_at for r in rows if r.published_at is not None]
    start = since or (min(times) if times else now)
    end = until or now
    unit = _timeline_unit(start, end)
    step = STEPS[unit]
    buckets: dict[datetime, dict] = {}
    t = _bucket_start(start, unit)
    while t <= end and len(buckets) < 2000:
        buckets[t] = {"t": t, "bullish": 0, "neutral": 0, "bearish": 0}
        t += step
    for r in rows:
        if r.published_at is None:
            continue
        b = buckets.get(_bucket_start(r.published_at, unit))
        if b is not None:
            b[r.sentiment if r.sentiment in ("bullish", "bearish") else "neutral"] += 1
    return {"unit": unit, "buckets": list(buckets.values())}


@router.get("/summary")
def get_summary(
    window: tuple = Depends(_window_params),
    market: str | None = MARKET_PARAM,
    symbols: str | None = Query(None, description="Tickers to always include in `tickers` (e.g. a watchlist)"),
    top: int = Query(30, ge=0, le=200, description="How many of the most discussed tickers to return"),
    db: Session = Depends(get_db),
):
    """
    Everything the dashboard shows about a window, computed here so a range of any size costs
    the browser one small response: totals, sentiment, sectors, most discussed tickers, the
    sentiment timeline (5-minute bars up to 2 hours, 15-minute up to 12, hourly up to 3 days, daily
    up to ~a year, weekly beyond) and top picks.
    """
    since, until = window
    wanted = sorted({s.strip().upper() for s in (symbols or "").split(",") if s.strip()})[:100]
    minute = lambda d: d.replace(second=0, microsecond=0) if d else None  # noqa: E731 — cache key granularity
    key = (minute(since), minute(until), market, tuple(wanted), top)
    if key in _summary_cache:
        return _summary_cache[key]

    rows = _window_rows(db, since, until, market)
    finviz = _window_finviz_tickers(db, since, until, market)
    per_article = {r.id: set(r.tickers or []) | finviz.get(r.id, set()) for r in rows}
    invalid = invalid_symbols(db, {t for ts in per_article.values() for t in ts})
    per_article = {aid: sorted(ts - invalid) for aid, ts in per_article.items()}
    sector_of = sector_lookup(db, {t for ts in per_article.values() for t in ts})

    total = _tally()
    sectors: dict[str, dict] = defaultdict(_tally)
    tickers: dict[str, dict] = defaultdict(_tally)
    latest: dict[str, tuple[datetime, int]] = {}
    for r in rows:
        verified = r.status == "verified"
        _add(total, r.sentiment, verified)
        syms = per_article[r.id]
        _add(sectors[primary_sector(syms, sector_of, r.sector)], r.sentiment, verified)
        for s in syms:
            _add(tickers[s], r.sentiment, verified)
            when = r.published_at or datetime.min.replace(tzinfo=UTC)
            if s not in latest or when > latest[s][0]:
                latest[s] = (when, r.id)

    ranked = sorted(tickers, key=lambda s: (-tickers[s]["count"], s))[:top]
    chosen = list(dict.fromkeys([*ranked, *wanted]))
    headlines = dict(db.execute(
        select(Article.id, Article.headline).where(Article.id.in_([latest[s][1] for s in chosen if s in latest]))
    ).all()) if chosen else {}

    def ticker_out(s: str) -> dict:
        when, aid = latest.get(s, (None, None))
        return {"symbol": s, **(tickers.get(s) or _tally()),
                "latest": {"id": aid, "headline": headlines.get(aid), "published_at": when} if aid else None}

    pick_ids = pick_ids_for_window(db, since, until)
    if market and pick_ids:
        pick_ids = set(db.execute(select(Article.id).where(Article.id.in_(pick_ids), Article.market == market)).scalars())
    result = {
        "since": since,
        "until": until,
        **total,
        "sectors": [{"name": n, **t} for n, t in sorted(sectors.items(), key=lambda kv: (-kv[1]["count"], kv[0]))],
        "tickers": [ticker_out(s) for s in chosen],
        "timeline": _timeline(rows, _not_before_first_story(db, since), until),
        "picks": len(pick_ids),
    }
    _summary_cache[key] = result
    return result


@router.get("/sectors")
def get_sectors(
    window: tuple = Depends(_window_params),
    market: str | None = MARKET_PARAM,
    db: Session = Depends(get_db),
):
    """Sectors with extracted news in the window (default: last 3 days), busiest first."""
    since, until = window
    if since is None and until is None:
        since = datetime.now(UTC) - timedelta(days=3)
    summary = get_summary((since, until), market=market, symbols=None, top=0, db=db)
    return {"sectors": [{"name": s["name"], "count": s["count"]} for s in summary["sectors"]]}


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """Pipeline status breakdown (for monitoring)."""
    by_status = dict(db.execute(select(Article.status, func.count()).group_by(Article.status)).all())
    return {"articles_by_status": by_status, "total_articles": sum(by_status.values())}
