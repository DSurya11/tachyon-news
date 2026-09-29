# Tachyon News — dashboard (v2)

A trading-terminal style front end for the stock-news pipeline. Plain HTML, CSS and ES modules:
no framework, no build step, no dependencies.

The previous single-page version is preserved in [`../v1-classic/`](../v1-classic/).

## Run it
```bash
make up              # API on :8080 + dashboard on :3000
make dev-frontend    # dashboard only
```
It must be served over HTTP (ES modules don't load from `file://`).

| URL option | Effect |
|---|---|
| *(none)* | `localhost` → `http://localhost:8080`; elsewhere → `PROD_API_URL` in [js/config.js](js/config.js) |
| `?api=https://…` | Use a specific API |
| `?demo=1` | Built-in demo data (also used automatically when the API is unreachable, with a banner) |

## What's in it

**Layout.** Left rail (views, sectors ranked by volume with sentiment bars, pipeline health and data
readiness), the main view, and a right-hand inspector that becomes a drawer on laptops and a full-screen
sheet on phones (with a bottom tab bar).

**Overview.** KPIs (24h volume, verified %, market mood, active sectors, most-mentioned ticker), the
daily-brief teaser, a 48-hour stacked sentiment timeline, a sector heatmap (size = volume, colour =
net sentiment), most-mentioned tickers with live price and 30-day sparkline, and the latest verified stories.

**Feed.** Every extracted story from the last 3 days grouped by day. Filters for text, sentiment, sector,
event type, time window and verified-only all live in the URL, so filtered views are shareable. Compact
and comfortable densities, `j`/`k` navigation, new stories highlighted on refresh without losing your
scroll position.

**Daily brief.** The AI report with a sticky table of contents (scroll-spy), `[id]` citations that
preview the source on hover and open it on click, a history selector for previous days, and the full
list of source articles.

**Watchlist.** Star any ticker (stored in this browser) to track price, 30-day trend, news volume,
sentiment and the latest headline.

**Inspectors.**
- **Story:** summary, verification status, key facts, numbers, evidence quote, tickers with live moves,
  and whether it is cited in today's brief.
- **Ticker:** live or last-close quote, an interactive 30-day chart with crosshair, 30-day stats, a news
  sentiment split, 30 days of news, the TradingView advanced chart and a Yahoo Finance link.

**Everywhere.**
- ⌘K / Ctrl K command palette (tickers, sectors, stories, views; any symbol can be looked up).
- Live NYSE session status (pre-market, open, after hours, closed) with a countdown.
- A market tape.
- Light and dark themes (follows the OS preference, `t` toggles).
- Shareable URLs with a working back button.
- Keyboard shortcuts (`?`).
- Reduced-motion support.
- Report Markdown is rendered by a small renderer that escapes everything first, so model output
  can't inject HTML.

**Efficient by design.** One `/news` call feeds every view. Quotes are batched (`/quotes`, 50 per
request), cached for 60 s, and ticker-chip quotes load only for rows scrolled into view. Polling runs
every 60 s and pauses in background tabs.

## Files
```
index.html            app shell
css/tokens.css        design tokens (both themes)
css/app.css           layout and components
js/config.js          API URL + refresh settings
js/main.js            boot, polling, routing, shortcuts, rail/tape/tab bar
js/router.js          hash routes (#/feed?sector=…&a=123)
js/store.js           state + event bus (watchlist/theme persisted)
js/api.js             API client, caches, demo fallback
js/views/*.js         overview, feed, brief, watchlist
js/inspector.js       story + ticker panels
js/overlays.js        command palette, shortcuts, TradingView modal
js/components.js      shared fragments, lazy quote hydration
js/charts.js          SVG sparkline, price chart, sentiment bars
js/markdown.js        safe Markdown renderer
js/util.js            formatting, market clock, derived stats
js/mock.js            demo data
```
A browser test (`tests/e2e/test_dashboard.py`) drives these views in headless Chromium.
