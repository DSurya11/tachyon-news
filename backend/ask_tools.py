"""
backend/ask_tools.py
────────────────────
The Ask agent's tools (backend/ask.py): read-only queries over Tachyon's own stories and prices.

Every number the agent may state comes back from here, computed by code: how many stories match,
a price change between two sessions, how a story's stocks moved after it. The model only chooses
which tool to call with which filters. Each tool takes the session and keyword arguments and
returns JSON text for the model; bad arguments raise ToolError, which the model is shown.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, or_, select, union_all
from sqlalchemy.orm import Session

from backend.routers.news import SENTIMENTS, get_article, get_news
from pipeline.db.models import Article, ArticleTicker, EventOutcome, Extraction, PriceDaily, Ticker
from pipeline.db.queries import MACRO_SECTOR

MAX_STORIES = 20
MAX_SYMBOLS = 10
EVENTS = ("earnings", "merger", "product", "regulatory", "legal", "personnel", "macro", "other")
SECTORS = ("Technology", "Health Care", "Financials", "Industrials", "Consumer Discretionary",
           "Communication Services", "Materials", "Consumer Staples", "Energy", "Real Estate",
           "Utilities", MACRO_SECTOR)


class ToolError(ValueError):
    """A call the model can fix: told to it as the tool's result."""


def _day(value: str | None, name: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError as exc:
        raise ToolError(f"{name} must be a date like 2026-10-05") from exc


def _pct(value) -> float | None:
    return None if value is None else round(float(value) * 100, 2)


def newest_story(db: Session) -> datetime | None:
    return db.scalar(select(func.max(Article.published_at)))


def search_stories(db: Session, words: str | None = None, ticker: str | None = None, sector: str | None = None,
                   sentiment: str | None = None, event: str | None = None, market: str | None = None,
                   since: str | None = None, until: str | None = None, verified_only: bool = False,
                   limit: int = 10) -> str:
    if sentiment and sentiment not in SENTIMENTS:
        raise ToolError(f"sentiment must be one of {sorted(SENTIMENTS)}")
    if event and event not in EVENTS:
        raise ToolError(f"event must be one of {list(EVENTS)}")
    if sector and sector not in SECTORS:
        raise ToolError(f"sector must be one of {list(SECTORS)}")
    if market and market not in ("global", "india"):
        raise ToolError("market must be global (US and world news) or india")
    if words and len(words) > 100:
        raise ToolError("words: at most 100 characters")
    start, end = _day(since, "since"), _day(until, "until")
    window = (datetime.combine(start, datetime.min.time(), UTC) if start else None,
              datetime.combine(end + timedelta(days=1), datetime.min.time(), UTC) if end else None)
    found = get_news(window=window, sector=sector, ticker=ticker, trading_day=None, q=words, market=market,
                     status="verified,extracted", sentiment=sentiment, event=event, verified_only=bool(verified_only),
                     picks=False, ids=None, page=1, limit=max(1, min(int(limit), MAX_STORIES)), db=db)
    moves = _day0_moves(db, [a["id"] for a in found["articles"]])
    out = {
        "total_matching": found["total"],
        "stories": [{
            "id": a["id"], "headline": a["headline"], "published": a["published_at"].isoformat()[:16] if a["published_at"] else None,
            "source": a["source_name"], "market": a["market"], "tickers": a["tickers"], "sector": a["sector"],
            "sentiment": a["sentiment"], "event": a["event_type"], "summary": a["one_line"], "verified": a["verified"],
            **({"moved_day0": moves[a["id"]]} if a["id"] in moves else {}),
        } for a in found["articles"]],
    }
    if not found["total"]:
        newest = newest_story(db)
        out["newest_story_in_database"] = newest.date().isoformat() if newest else None
    return json.dumps(out, ensure_ascii=False)


def _day0_moves(db: Session, ids: list[int]) -> dict[int, list[dict]]:
    """Story id → each stock's day-0 move after it and the benchmark's, in percent (event_outcomes)."""
    out: dict[int, list[dict]] = {}
    if ids:
        for m in db.execute(select(EventOutcome).where(EventOutcome.article_id.in_(ids))).scalars():
            out.setdefault(m.article_id, []).append({"ticker": m.ticker, "day0_pct": _pct(m.ret_day0),
                                                     "benchmark_day0_pct": _pct(m.bench_day0)})
    return out


def get_story(db: Session, story_id: int) -> str:
    try:
        story = get_article(int(story_id), db)
    except HTTPException as exc:
        raise ToolError(f"no story with id {story_id}") from exc
    except (TypeError, ValueError) as exc:
        raise ToolError("story_id must be a number from search_stories") from exc
    ext = story["extraction"] or {}
    moves = db.execute(select(EventOutcome).where(EventOutcome.article_id == story["id"])).scalars().all()
    return json.dumps({
        "id": story["id"], "headline": story["headline"], "source": story["source_name"], "url": story["url"],
        "published": story["published_at"].isoformat()[:16] if story["published_at"] else None,
        "tickers": story["tickers"], "sentiment": story["sentiment"], "event": story["event_type"],
        "verified": story["verified"], "summary": ext.get("one_line"), "key_facts": ext.get("key_facts"),
        "numbers": ext.get("numbers"),
        # Moves after the story, in percent: last close before it → first close after it (day 0),
        # one and five sessions later, beside the benchmark over the same days.
        "moves_after": [{
            "ticker": m.ticker, "benchmark": m.benchmark, "day0": m.day0_date.isoformat(),
            "day0_pct": _pct(m.ret_day0), "plus_1d_pct": _pct(m.ret_1d), "plus_5d_pct": _pct(m.ret_5d),
            "benchmark_day0_pct": _pct(m.bench_day0), "benchmark_plus_1d_pct": _pct(m.bench_1d),
            "benchmark_plus_5d_pct": _pct(m.bench_5d),
        } for m in moves],
    }, ensure_ascii=False)


def price_move(db: Session, symbols: list[str], start: str, end: str) -> str:
    first, last = _day(start, "start"), _day(end, "end")
    if isinstance(symbols, str):
        symbols = [symbols]
    wanted = list(dict.fromkeys(s.strip().upper() for s in symbols or [] if s and s.strip()))
    if not wanted or first is None or last is None:
        raise ToolError("price_move needs symbols, start and end")
    if len(wanted) > MAX_SYMBOLS:
        raise ToolError(f"at most {MAX_SYMBOLS} symbols a call")
    if first > last:
        raise ToolError("start is after end")
    rows = db.execute(
        select(PriceDaily.ticker, PriceDaily.date, PriceDaily.close)
        .where(PriceDaily.ticker.in_(wanted), PriceDaily.date >= first, PriceDaily.date <= last, PriceDaily.close.is_not(None))
        .order_by(PriceDaily.ticker, PriceDaily.date)
    ).all()
    closes: dict[str, list] = {}
    for sym, day, close in rows:
        closes.setdefault(sym, []).append((day, float(close)))
    moves = []
    for sym in wanted:
        series = closes.get(sym, [])
        if len(series) < 2:
            moves.append({"symbol": sym, "error": f"fewer than two closes between {first} and {last}; "
                          "find_ticker gives exact symbols (Indian ones end in .NS)"})
            continue
        (d0, c0), (d1, c1) = series[0], series[-1]
        moves.append({"symbol": sym, "from": {"date": d0.isoformat(), "close": c0}, "to": {"date": d1.isoformat(), "close": c1},
                      "change_pct": round((c1 / c0 - 1) * 100, 2), "sessions": len(series)})
    return json.dumps({"moves": moves})


def find_ticker(db: Session, name: str) -> str:
    needle = (name or "").strip()
    if len(needle) < 2:
        raise ToolError("name: at least 2 characters")
    like = f"%{needle.replace('%', '').replace('_', '')}%"
    rows = db.execute(
        select(Ticker.symbol, Ticker.company_name, Ticker.sector)
        .where(or_(Ticker.symbol == needle.upper(), Ticker.company_name.ilike(like))).limit(10)
    ).all()
    found = [{"symbol": s, "company": c, "sector": sec, "stories": None} for s, c, sec in rows]
    # Indian listings are not in the tickers table (it comes from Finviz), and their symbols
    # often shorten the name (Tata Motors: TATAMOT.NS on stories), so symbols that start with
    # the name or its first word, from the stories, with how many stories name each.
    words = re.sub(r"[^A-Z0-9 ]", "", needle.upper()).split()
    prefixes = {p for p in ("".join(words), words[0] if words else "") if len(p) >= 3}
    if prefixes:
        symbols = union_all(select(ArticleTicker.ticker.label("t")),
                            select(func.unnest(Extraction.tickers).label("t"))).subquery()
        named = db.execute(
            select(symbols.c.t, func.count()).where(or_(*(symbols.c.t.like(f"{p}%") for p in prefixes)))
            .group_by(symbols.c.t).order_by(func.count().desc()).limit(10)
        ).all()
        known = {f["symbol"] for f in found}
        found += [{"symbol": s, "company": None, "sector": None, "stories": n} for s, n in named if s not in known]
    return json.dumps({"matches": found[:10],
                       "note": "No symbol? search_stories with words= finds stories by name."}, ensure_ascii=False)


FUNCTIONS = {"search_stories": search_stories, "get_story": get_story, "price_move": price_move,
             "find_ticker": find_ticker}

SCHEMAS = [
    {"type": "function", "function": {
        "name": "search_stories",
        "description": "Stories (newest first) matching all the given filters, how many match in total, and for each story how its stocks moved on the first close after it (moved_day0).",
        "parameters": {"type": "object", "properties": {
            "words": {"type": "string", "description": "Words to find in the headline, summary or source."},
            "ticker": {"type": "string", "description": "Exact symbol, e.g. NVDA or TATAMOTORS.NS (find_ticker finds it)."},
            "sector": {"type": "string", "enum": list(SECTORS)},
            "sentiment": {"type": "string", "enum": sorted(SENTIMENTS)},
            "event": {"type": "string", "enum": list(EVENTS)},
            "market": {"type": "string", "enum": ["global", "india"]},
            "since": {"type": "string", "description": "First day, YYYY-MM-DD."},
            "until": {"type": "string", "description": "Last day, YYYY-MM-DD (included)."},
            "verified_only": {"type": "boolean", "description": "Only stories whose quote and numbers matched the source."},
            "limit": {"type": "integer", "minimum": 1, "maximum": MAX_STORIES},
        }},
    }},
    {"type": "function", "function": {
        "name": "get_story",
        "description": "One story in full: key facts, numbers, source link, and how its stocks moved after it.",
        "parameters": {"type": "object", "properties": {"story_id": {"type": "integer"}}, "required": ["story_id"]},
    }},
    {"type": "function", "function": {
        "name": "price_move",
        "description": "Each stock's change between its first and last daily close in a date range, computed from stored prices. Several symbols in one call.",
        "parameters": {"type": "object", "properties": {
            "symbols": {"type": "array", "items": {"type": "string"}, "maxItems": MAX_SYMBOLS},
            "start": {"type": "string", "description": "YYYY-MM-DD"},
            "end": {"type": "string", "description": "YYYY-MM-DD"}}, "required": ["symbols", "start", "end"]},
    }},
    {"type": "function", "function": {
        "name": "find_ticker",
        "description": "Symbols for a company name or symbol prefix (e.g. 'Tata Motors', 'HDFC').",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
    }},
]
