import sys

with open('pipeline/prices/finnhub.py', 'r') as f:
    content = f.read()

replacement = """_free_tier_ban = False

def fetch_candles(ticker: str, start_ts: int, end_ts: int) -> Optional[dict]:
    \"\"\"Fetch daily candles from Finnhub.\"\"\"
    global _free_tier_ban
    if _free_tier_ban:
        return None

    url = "https://finnhub.io/api/v1/stock/candle"
    params = {
        "symbol": ticker,
        "resolution": "D",
        "from": start_ts,
        "to": end_ts,
        "token": settings.finnhub_api_key
    }
    
    if settings.finnhub_api_key == "your_finnhub_key_here" or not settings.finnhub_api_key:
        logger.error(f"Finnhub API key not configured. Cannot fetch data for {ticker}.")
        return None

    try:
        resp = httpx.get(url, params=params, timeout=10.0)
        if resp.status_code == 403:
            logger.warning("Finnhub Free Tier doesn't support /candle. Disabling price fetch for this run.")
            _free_tier_ban = True
            return None
        resp.raise_for_status()
        data = resp.json()
        if data.get("s") == "ok":
            return data
        return None
    except Exception as e:
        logger.error(f"Error fetching Finnhub data for {ticker}: {e}")
        return None"""

import re
content = re.sub(r'def fetch_candles.*?return None\n\n', replacement + '\n\n', content, flags=re.DOTALL)

with open('pipeline/prices/finnhub.py', 'w') as f:
    f.write(content)
