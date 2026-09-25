# TERMINAL // Stock News Intelligence

Static, dependency-free rebuild of the dashboard. No Node, no build step, no framework.

## Run it
Open `index.html` in a browser. That's it.
(Or serve the folder: `python3 -m http.server 8000` → http://localhost:8000)

The Google Fonts and the TradingView chart need an internet connection.

## Connect your backend
Edit `js/config.js`:

```js
API_URL: "http://localhost:8000"
```

Endpoints used:

| Endpoint | Used for |
|---|---|
| `GET /health` | pipeline tile (`last_scrape_at`, `items_found`, `errors`) and optional `readiness` (0–100) for the readiness bar |
| `GET /news?sector=Technology` | article cards (called once per sector) |
| `GET /quote/{symbol}` | ticker badge price / % change, and the tape |
| `GET /candles/{symbol}?days=30` | sparkline |

Your backend must allow CORS from wherever this page is served.
If a call fails, that part falls back to mock data and an amber banner appears.
Leave `API_URL` empty to run purely on mock data.

## Files
- `index.html` – page structure
- `css/styles.css` – all styling and animation
- `js/config.js` – API URL, refresh interval, tape symbols
- `js/mock-data.js` – the 14 stories and 22 quotes from the original page
- `js/api.js` – fetch layer + mock fallback
- `js/app.js` – rendering, filters, search, lazy quotes, TradingView modal

## Features
Sector chips, headline/ticker search, manual + 15s auto refresh, lazy-loaded ticker badges (IntersectionObserver),
skeleton loaders, sparklines, click a ticker for a TradingView chart, Esc to close.
