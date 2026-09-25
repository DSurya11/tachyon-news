/*
  TERMINAL // Stock News — configuration

  API_URL
    ""  (empty)  -> runs entirely on built-in mock data (default, works offline)
    "http://localhost:8080" -> uses your real backend:
        GET /health
        GET /news?sector=Technology
        GET /quote/{symbol}
        GET /candles/{symbol}?days=30
    If the backend can't be reached, the page falls back to mock data
    and shows a warning banner.
*/
window.APP_CONFIG = {
  API_URL: "http://localhost:8080",
  REFRESH_MS: 15000,
  // Symbols shown in the scrolling tape under the header
  TAPE_SYMBOLS: ["AAPL","TSM","NVDA","AMD","MSFT","META","GOOGL","JPM","GS","WFC","BAC","TLT","SPY","XOM"]
};
