import logging
import time
from datetime import date, datetime, timedelta
from typing import Optional
import httpx

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select

from pipeline.config import settings
from pipeline.db.local import LocalSession
from pipeline.db.models import PriceDaily, Ticker

logger = logging.getLogger(__name__)


def fetch_candles(ticker: str, start_ts: int, end_ts: int) -> Optional[dict]:
    """Fetch daily candles from Finnhub."""
    url = "https://finnhub.io/api/v1/stock/candle"
    params = {
        "symbol": ticker,
        "resolution": "D",
        "from": start_ts,
        "to": end_ts,
        "token": settings.finnhub_api_key
    }
    
    if settings.finnhub_api_key == "your_finnhub_key_here":
        logger.warning(f"Finnhub API key not configured. Mocking data for {ticker}.")
        import hashlib
        import random
        # Seed the random generator with the ticker symbol so it's consistent across runs
        seed = int(hashlib.md5(ticker.encode()).hexdigest(), 16)
        rng = random.Random(seed)
        
        base_price = 20.0 + (seed % 480)
        c, h, l, o = [], [], [], []
        current_price = base_price
        
        for i in range(30):
            # random daily return between -3% and +3%
            daily_ret = (rng.random() - 0.5) * 0.06
            current_price *= (1 + daily_ret)
            
            o.append(round(current_price * 0.99, 2))
            c.append(round(current_price, 2))
            h.append(round(current_price * 1.02, 2))
            l.append(round(current_price * 0.98, 2))
            
        return {
            "c": c,
            "h": h,
            "l": l,
            "o": o,
            "t": [start_ts + (i * 86400) for i in range(30)],
            "v": [1000000] * 30,
            "s": "ok"
        }

    try:
        resp = httpx.get(url, params=params, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        if data.get("s") == "ok":
            return data
        return None
    except Exception as e:
        logger.error(f"Error fetching Finnhub data for {ticker}: {e}")
        return None


def update_prices(days_back: int = 30):
    """
    Fetch daily candles for all active tickers.
    Respects Finnhub free tier rate limit of 60 req/min (1 req/sec).
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    start_ts = int(start_date.timestamp())
    end_ts = int(end_date.timestamp())
    
    with LocalSession() as session:
        # Get all tickers
        tickers = session.execute(select(Ticker.symbol)).scalars().all()
        if not tickers:
            # If no tickers in DB yet, let's at least test with AAPL, NVDA, TSLA
            tickers = ["AAPL", "NVDA", "TSLA"]
            
        logger.info(f"Fetching prices for {len(tickers)} tickers.")
        
        for symbol in tickers:
            data = fetch_candles(symbol, start_ts, end_ts)
            if not data:
                continue
                
            # Upsert into prices_daily
            rows = []
            for i in range(len(data["t"])):
                dt = datetime.fromtimestamp(data["t"][i]).date()
                rows.append({
                    "ticker": symbol,
                    "date": dt,
                    "open": data["o"][i],
                    "high": data["h"][i],
                    "low": data["l"][i],
                    "close": data["c"][i],
                    "volume": data["v"][i]
                })
                
            if rows:
                stmt = insert(PriceDaily).values(rows)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["ticker", "date"],
                    set_={
                        "open": stmt.excluded.open,
                        "high": stmt.excluded.high,
                        "low": stmt.excluded.low,
                        "close": stmt.excluded.close,
                        "volume": stmt.excluded.volume,
                    }
                )
                session.execute(stmt)
                session.commit()
                
            # Rate limit: 1 request per second
            if settings.finnhub_api_key != "your_finnhub_key_here":
                time.sleep(1.0)
                
    logger.info("Finished updating prices.")


if __name__ == "__main__":
    update_prices()
