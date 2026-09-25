import json
from collections import defaultdict
from datetime import date
from typing import Optional

from sqlalchemy import select

from pipeline.db.models import Article, Extraction, Ticker


def build_report_prompt(session, trading_day: date) -> Optional[str]:
    """
    Builds the synthesis prompt for Claude.ai grouped by sector.
    Includes only sectors with >= 3 verified articles.
    """
    stmt = (
        select(Article, Extraction)
        .join(Extraction, Article.id == Extraction.article_id)
        .where(Article.trading_day == trading_day)
        .where(Article.status == "verified")
    )
    results = session.execute(stmt).all()
    
    if not results:
        return None

    # Fetch all known tickers to map extraction tickers -> sector
    all_tickers = {t.symbol: t.sector for t in session.execute(select(Ticker)).scalars()}
    
    sector_groups = defaultdict(list)
    
    for article, extraction in results:
        sectors_for_article = set()
        for sym in (extraction.tickers or []):
            sec = all_tickers.get(sym)
            if sec:
                sectors_for_article.add(sec)
        
        # If the LLM found no tickers (or none matched a known sector), it's Macro
        if not sectors_for_article:
            sectors_for_article.add("Macro")
            
        for sec in sectors_for_article:
            sector_groups[sec].append({
                "article_id": article.id,
                "headline": article.headline,
                "event_type": extraction.event_type,
                "sentiment": extraction.sentiment,
                "tickers": extraction.tickers,
                "key_facts": extraction.key_facts,
                "numbers": extraction.numbers,
                "one_line": extraction.one_line
            })

    # Filter sectors with >= 3 articles
    final_sectors = {}
    for sec, items in sector_groups.items():
        # deduplicate by article_id
        unique_items = list({item["article_id"]: item for item in items}.values())
        if len(unique_items) >= 3:
            final_sectors[sec] = unique_items
            
    if not final_sectors:
        return None

    prompt = [
        f"You are a financial analyst writing a daily market report for {trading_day}.",
        "Here are the extracted news events grouped by sector. They are in JSON format.",
        "Synthesize a cohesive, professional summary for each sector.",
        "",
        "CRITICAL INSTRUCTIONS:",
        "1. You MUST cite the [article_id] inline for every single claim you make (e.g. 'Apple announced new chips [104].').",
        "2. Do NOT hallucinate information outside of what is provided in the JSON.",
        "3. Format the report using clear Markdown, with an H2 (##) for each sector.",
        "4. Output ONLY the report markdown, no pleasantries or preamble.",
        "\n--- DATA START ---\n"
    ]
    
    for sec, items in sorted(final_sectors.items()):
        prompt.append(f"### SECTOR: {sec}")
        prompt.append(json.dumps(items, indent=2))
        prompt.append("\n")
        
    return "\n".join(prompt)
