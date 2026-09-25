import httpx
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from backend.db import get_db
from pipeline.config import settings
from pipeline.db.models import PriceDaily

from cachetools import TTLCache
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["quotes"])

# 5-minute TTL cache, max 1000 items
quote_cache = TTLCache(maxsize=1000, ttl=300)

def _fetch_quote_finnhub(symbol: str) -> dict:
    if symbol in quote_cache:
        return quote_cache[symbol]

    # If API key is dummy, return mock
    if settings.finnhub_api_key == "your_finnhub_key_here":
        data = {
            "symbol": symbol,
            "price": 150.0,
            "change": 1.5,
            "pct_change": 1.01,
            "t": 0
        }
        quote_cache[symbol] = data
        return data
        
    url = "https://finnhub.io/api/v1/quote"
    params = {"symbol": symbol, "token": settings.finnhub_api_key}
    try:
        resp = httpx.get(url, params=params, timeout=5.0)
        resp.raise_for_status()
        raw = resp.json()
        data = {
            "symbol": symbol,
            "price": raw.get("c", 0.0),
            "change": raw.get("d", 0.0),
            "pct_change": raw.get("dp", 0.0),
            "t": raw.get("t", 0)
        }
        quote_cache[symbol] = data
        return data
    except Exception as e:
        logger.error(f"Quote fetch error for {symbol}: {e}")
        return {"symbol": symbol, "error": "Could not fetch quote"}

@router.get("/quote/{symbol}")
def get_quote(symbol: str):
    """Live price + % change."""
    return _fetch_quote_finnhub(symbol.upper())

@router.get("/quotes")
def get_batch_quotes(symbols: str = Query(...)):
    """Batch quotes (max 50), comma-separated."""
    sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if len(sym_list) > 50:
        raise HTTPException(status_code=400, detail="Max 50 symbols allowed")
        
    results = []
    for sym in sym_list:
        results.append(_fetch_quote_finnhub(sym))
    return {"data": results}

@router.get("/candles/{symbol}")
def get_candles(symbol: str, days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    """OHLCV for sparklines from Neon database."""
    symbol = symbol.upper()
    candles = db.execute(
        select(PriceDaily)
        .where(PriceDaily.ticker == symbol)
        .order_by(desc(PriceDaily.date))
        .limit(days)
    ).scalars().all()
    
    # Return chronologically (oldest first)
    candles.reverse()
    
    return {
        "symbol": symbol,
        "candles": [c.close for c in candles]
    }
