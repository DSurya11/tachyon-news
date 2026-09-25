from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from backend.db import get_db
from pipeline.db.models import Article, Extraction, ArticleTicker, Ticker

router = APIRouter(prefix="/news", tags=["news"])

@router.get("")
def get_news(
    sector: Optional[str] = None,
    ticker: Optional[str] = None,
    trading_day: Optional[date] = None,
    status: Optional[str] = "verified",
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get paginated news feed, optionally filtered."""
    offset = (page - 1) * limit
    
    # Base query for articles
    stmt = select(Article).order_by(desc(Article.published_at))
    
    if status:
        stmt = stmt.where(Article.status == status)
    if trading_day:
        stmt = stmt.where(Article.trading_day == trading_day)
        
    if ticker:
        # Join ArticleTicker
        stmt = stmt.join(ArticleTicker, Article.id == ArticleTicker.article_id).where(ArticleTicker.ticker == ticker)
    elif sector:
        # Join ArticleTicker and Ticker to filter by sector
        stmt = stmt.join(ArticleTicker, Article.id == ArticleTicker.article_id)\
                   .join(Ticker, ArticleTicker.ticker == Ticker.symbol)\
                   .where(Ticker.sector == sector)
                   
    # Avoid duplicate rows if joined on multiple tickers
    if ticker or sector:
        stmt = stmt.distinct()
        
    # Execute query with pagination
    # We join Extraction to provide UI fields
    stmt = select(Article, Extraction).outerjoin(Extraction, Article.id == Extraction.article_id)
    if status:
        stmt = stmt.where(Article.status == status)
    if trading_day:
        stmt = stmt.where(Article.trading_day == trading_day)
    if ticker:
        stmt = stmt.join(ArticleTicker, Article.id == ArticleTicker.article_id).where(ArticleTicker.ticker == ticker)
    elif sector:
        stmt = stmt.join(ArticleTicker, Article.id == ArticleTicker.article_id)\
                   .join(Ticker, ArticleTicker.ticker == Ticker.symbol)\
                   .where(Ticker.sector == sector)
                   
    stmt = stmt.order_by(desc(Article.published_at))
        
    rows = db.execute(stmt.offset(offset).limit(limit)).all()
    
    results = []
    seen = set()
    for a, ext in rows:
        if a.id in seen:
            continue
        seen.add(a.id)
        results.append({
            "id": a.id,
            "headline": a.headline,
            "source_name": a.source_name,
            "canonical_url": a.canonical_url,
            "published_at": a.published_at,
            "trading_day": a.trading_day,
            "status": a.status,
            "noise_tags": a.noise_tags,
            "event_type": ext.event_type if ext else None,
            "sentiment": ext.sentiment if ext else None,
            "tickers": ext.tickers if ext else [],
            "one_line": ext.one_line if ext else None
        })
        
    return {
        "page": page,
        "limit": limit,
        "articles": results
    }

@router.get("/{id}")
def get_article(id: int, db: Session = Depends(get_db)):
    """Get single article with its extraction data."""
    article = db.execute(select(Article).where(Article.id == id)).scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
        
    extraction = db.execute(select(Extraction).where(Extraction.article_id == id)).scalar_one_or_none()
    
    return {
        "id": article.id,
        "headline": article.headline,
        "source_name": article.source_name,
        "canonical_url": article.canonical_url,
        "published_at": article.published_at,
        "trading_day": article.trading_day,
        "status": article.status,
        "extraction": {
            "event_type": extraction.event_type if extraction else None,
            "sentiment": extraction.sentiment if extraction else None,
            "tickers": extraction.tickers if extraction else None,
            "key_facts": extraction.key_facts if extraction else None,
            "numbers": extraction.numbers if extraction else None,
            "one_line": extraction.one_line if extraction else None,
            "evidence": extraction.evidence if extraction else None
        } if extraction else None
    }
