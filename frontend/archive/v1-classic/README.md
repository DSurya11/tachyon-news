# TACHYON NEWS // Stock News dashboard

Static, dependency-free dashboard: no Node, no build step, no framework.

## Run it
`make up` from the repo root (serves it on http://localhost:3000 next to the API on :8080),
or `python3 -m http.server 3000` in this folder. Opening `index.html` directly also works.
Google Fonts and the TradingView chart need an internet connection.

## Connect the backend
[js/config.js](js/config.js) picks the API automatically:
- served from `localhost` / `file://` → `http://localhost:8080`
- anywhere else → `PROD_API_URL` (set it to your Render URL before deploying)

If the API can't be reached the page falls back to built-in mock data and shows an amber banner.
The API must allow the page's origin (`CORS_ORIGINS`).

| Endpoint | Used for |
|---|---|
| `GET /health` | pipeline tile (last scrape, items, errors, amber dot when degraded) and readiness bar |
| `GET /news?days=3&limit=200` | the feed; grouped client-side by each article's `sector` |
| `GET /reports/latest` | the Daily Brief panel (Markdown; `[123]` citations jump to the article card) |
| `GET /news/{id}` | opening a cited article that is outside the current feed window |
| `GET /quote/{symbol}` | ticker badges and the tape |
| `GET /candles/{symbol}?days=30` | sparklines |

## Files
- `index.html` – page structure
- `css/styles.css` – styling and animation
- `js/config.js` – API URL, refresh interval, feed window, tape symbols
- `js/mock-data.js` – offline stories, quotes and report
- `js/api.js` – fetch layer + mock fallback
- `js/app.js` – rendering, sectors, report Markdown renderer, filters, search, lazy quotes, TradingView modal

## Features
Daily AI brief with clickable citations, sector chips built from live data, headline links to the source,
✓ badges for evidence-verified extractions, search, manual + 60 s auto refresh (paused in background tabs),
lazy-loaded ticker badges with sparklines, TradingView chart on ticker click (Esc closes).

Report Markdown is rendered by a small built-in renderer that escapes everything first, so model
output can never inject HTML.
