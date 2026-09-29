"""
pipeline/report/prompt_builder.py
─────────────────────────────────
Builds the daily market-report prompt from the day's extracted articles.

Articles are grouped by GICS sector (via the tickers Finviz attached to the
row plus the tickers the LLM confirmed).  Articles with no known sector go
under "Macro & Markets".  Verified articles are listed first and flagged so
the writer can weight them; each sector is capped to keep the prompt small.
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pipeline.config import settings
from pipeline.db.models import Article, Extraction
from pipeline.db.queries import article_tickers, primary_sector, sector_lookup

REPORTABLE_STATUSES = ("verified", "extracted")
INDIA_GROUP = "India Markets"

SYSTEM_TEMPLATE = """\
You are a sell-side market strategist writing the daily pre-market brief for a
public dashboard. You receive structured news extractions grouped by sector.

Write the report in Markdown:
1. Start with "## Market Overview": 3-5 sentences on the day's dominant themes.
2. Then one "## <Sector>" section per sector with material news: a short
   synthesis paragraph followed by 2-5 bullet points of the most important items.
   Skip sectors whose news is trivial.
3. If an "India Markets" group is present, write one "## India Markets" section for it
   (same shape as a sector section) just before "What to Watch".
4. End with "## What to Watch": 3-5 bullets on catalysts and open questions.
5. After the report, output a ranking of the {top_n} stories a busy investor must read today,
   most important first, across all sectors and markets, as this exact block:
   ```json
   {{"top_picks": [{{"id": 1042, "why": "<max 14 words: why it matters>"}}]}}
   ```
   Rank by market impact and novelty, not by recency. Use only ids from the data.
   The block is removed before publishing; write nothing after it.

Rules:
- Cite the source article id in square brackets after every claim, e.g. "Nvidia raised guidance [1042]."
  Use only ids present in the data. Multiple sources: [1042][1057].
- Use only facts present in the data. Do not invent prices, numbers or events.
- Items marked "verified": false were not fully grounded against the article text — hedge
  their specifics ("reportedly") or omit them.
- Be concise and neutral; this is not investment advice. No preamble or sign-off.
"""


@dataclass
class ReportPrompt:
    trading_day: date
    system: str
    user: str
    article_ids: list[int]
    sectors: dict[str, int]

    @property
    def combined(self) -> str:
        """Single-message form for chat UIs that have no system prompt field."""
        return f"{self.system}\n\n{self.user}"


def _fit_budget(groups: dict[str, list[dict]], max_chars: int) -> None:
    """Drop the lowest-priority item from the largest sector until the data fits."""
    def size() -> int:
        return sum(len(json.dumps(items, ensure_ascii=False)) for items in groups.values())

    while size() > max_chars:
        largest = max(groups, key=lambda k: len(groups[k]))
        if len(groups[largest]) <= 1:
            break
        groups[largest].pop()


def count_reportable_articles(session: Session, trading_day: date, extracted_after: datetime | None = None) -> int:
    """Usable articles for the day, optionally only those extracted after a timestamp."""
    stmt = (
        select(func.count())
        .select_from(Article)
        .join(Extraction, Extraction.article_id == Article.id)
        .where(Article.trading_day == trading_day, Article.status.in_(REPORTABLE_STATUSES))
    )
    if extracted_after is not None:
        stmt = stmt.where(Extraction.created_at > extracted_after)
    return session.execute(stmt).scalar_one()


def build_report_prompt(session: Session, trading_day: date) -> ReportPrompt | None:
    rows = session.execute(
        select(Article, Extraction)
        .join(Extraction, Article.id == Extraction.article_id)
        .where(Article.trading_day == trading_day, Article.status.in_(REPORTABLE_STATUSES))
        .order_by((Article.status == "verified").desc(), Article.published_at.desc().nulls_last())
    ).all()
    if not rows:
        return None

    tickers_by_article = article_tickers(session, [a.id for a, _ in rows], {a.id: e.tickers for a, e in rows})
    sector_of = sector_lookup(session, {t for ts in tickers_by_article.values() for t in ts})

    groups: dict[str, list[dict]] = defaultdict(list)
    for article, ext in rows:
        tickers = tickers_by_article[article.id]
        # Indian stories get their own section; everything else is grouped by sector.
        sector = INDIA_GROUP if article.market == "india" else primary_sector(tickers, sector_of, ext.sector)
        if len(groups[sector]) >= settings.report_max_articles_per_sector:
            continue
        item = {
            "id": article.id,
            "headline": article.headline,
            "event": ext.event_type,
            "sentiment": ext.sentiment,
            "tickers": tickers[:6],
            "summary": ext.one_line,
            "facts": (ext.key_facts or [])[:2],
        }
        if article.status != "verified":
            item["verified"] = False
        groups[sector].append(item)

    _fit_budget(groups, settings.report_max_prompt_chars)

    used_ids = sorted({item["id"] for items in groups.values() for item in items})
    sections = [f"### SECTOR: {sector}\n{json.dumps(items, ensure_ascii=False)}" for sector, items in sorted(groups.items())]
    user = (
        f"Trading day: {trading_day.isoformat()} (US equities; Indian stories are grouped under '{INDIA_GROUP}')\n"
        f"Articles: {len(used_ids)} across {len(groups)} sectors.\n\n"
        "--- DATA START ---\n" + "\n\n".join(sections) + "\n--- DATA END ---"
    )
    return ReportPrompt(
        trading_day=trading_day,
        system=SYSTEM_TEMPLATE.format(top_n=settings.report_top_picks),
        user=user,
        article_ids=used_ids,
        sectors={s: len(items) for s, items in groups.items()},
    )
