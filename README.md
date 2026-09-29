# Tachyon News

Checked market news for US and Indian stocks. An hourly pipeline turns the
[Finviz news feed](https://finviz.com/news?v=3) and Indian market RSS feeds into structured, source-grounded stories,
writes a cited daily brief, and serves it all through an API to the **Tachyon News** dashboard
(**https://tachyon-news.vercel.app**, sign-in required). Personal use.

```
 Finviz + India RSS ──► M1 scrape ──► M2 body fetch ──► M3 LLM extraction ──► M4 daily brief
 (Playwright)              noise tags    httpx+trafilatura   + grounding check       cited, with top picks
        M5 prices (yfinance) ──► M5b story outcomes ──► local Postgres ──► M6 Neon sync
        local Postgres ──► FastAPI on the laptop ──► Tailscale Funnel ──► dashboard on Vercel
```

### The dashboard

- **One time range for everything**: last hour … last 12 months, all time, or custom dates (default: last 24 hours).
  Counts, sectors, charts and the wire are computed by the API, so it stays fast however much news piles up.
- **The wire**: every story with sentiment, event type, sector and tickers; server-side search, filters (sentiment,
  sector, event, verified only) and paging. **Top picks**: the stories the daily brief ranked, with the reason.
- **Daily brief**: sector-by-sector, every claim linked to its source story.
- **Stock panel**: live quote and a chart for 1D (with pre-market and after-hours) · 5D · 1M · 3M · 6M · 1Y · 5Y,
  with the change, range, stories and sentiment for the same span. Several panels open side by side on a laptop.
- **Priced in?** On each story: how far its stocks have moved since the headline, beyond the S&P 500 / Nifty 50, and,
  once enough history has built up, what similar stories (same event type and sentiment) were followed by: the
  usual move and how often the first-day move kept going or faded. History, never a forecast.
- Watchlist, search (Ctrl K), US / India / all markets, prices in local currency, USD or INR, dark and light themes.

| Stage | What it does |
|---|---|
| **M1 Scrape** | Headless Chromium loads Finviz, parses ~90 rows (headline, source, age, tickers, % moves), dedups by canonical URL, tags routine noise (law-firm ads, dividend notices, Nasdaq letters, stock blurbs). |
| **M1b India** | Pulls Indian market news from publisher RSS feeds (Economic Times, Mint, Business Standard) into the same flow, tagged `market = india`. |
| **M2 Fetch** | Downloads article bodies concurrently (20 global / 3 per domain), extracts text with trafilatura, skips hard paywalls, retries only transient errors, per-domain circuit breaker. |
| **M3 Extract** | An LLM (via [OmniRoute](https://github.com/diegosouzapw/OmniRoute)) returns tickers, event type, sentiment, facts, numbers, a one-line summary and a verbatim evidence quote. The **verifier** checks the quote and every number against the article body → `verified` or `extracted`. Failures are retried on later runs (max 3); router outages never burn an article's attempts. |
| **M4 Report** | Writes a sector-by-sector daily brief with `[article-id]` citations (plus an "India Markets" section), and ranks the day's must-read stories with a one-line reason — the dashboard's **Top picks**. Providers are tried in order: Claude API → Claude.ai browser → OmniRoute. Rewritten only when enough new articles arrive. |
| **M5 Prices** | Daily candles for tickers mentioned in the last 30 days, plus the S&P 500 and Nifty 50 benchmarks. |
| **M5b Outcomes** | For each story, the stock's move from the last close before the headline to the first close after it, one session later and five sessions later, beside the benchmark's (`event_outcomes`). The history behind the priced-in meter. |
| **M6 Sync** | Upserts the public subset to Neon (article bodies, evidence quotes and key facts never leave the laptop). Incremental. |

Article lifecycle: `new → body_fetched → verified | extracted | extraction_failed`, or `new → noise_tagged`.
Trading days close at 4 PM ET; after-hours and weekend news roll to the next session.

---

## Quick start

Prerequisites: Python 3.11+, Docker, Node 22 (OmniRoute and the dashboard), a Finnhub key (free) for live quotes.
Optional: [Tailscale](https://tailscale.com) (to reach the API from the hosted dashboard) and the Vercel CLI.

```bash
git clone https://github.com/DSurya11/tachyon-news && cd tachyon-news
make setup            # venv, dependencies, Playwright Chromium, .env from template
$EDITOR .env          # see "Configuration"
make db-up            # Postgres 16 in Docker
make migrate          # create/upgrade tables (local + Neon if configured)

npm i -g omniroute    # one-time: open http://localhost:20128, add Gemini/Groq keys,
                      # create a combo named "extraction-combo"
make run-pipeline     # one full run, to check the setup
make up               # everything up: installs it the first time (tests, snapshot, systemd), then checks it all
make down             # everything off, and it stays off after a reboot
```

Open **http://localhost:3000** (or the hosted dashboard). See [Running it day to day](#running-it-day-to-day) for what
`make up` sets up. While developing, `make dev-up` / `make dev-down` run OmniRoute, the API and the dashboard from the
working tree instead.

For a snappy local dashboard, set `API_DB_URL=$LOCAL_DB_URL` in `.env`; otherwise the API reads Neon (~2 s per query).

## Running it day to day

`make up` turns the laptop into a small production box for personal use. One command, safe to repeat: it starts
Docker and Postgres, installs everything with `make deploy` the first time, starts the services and timers, lets them run
without a login session (so they come back after a reboot), opens the Tailscale Funnel the hosted dashboard reaches the
API through, waits until it all answers and finishes with `make doctor`, including the hosted site and the tunnel as
seen from outside (`PUBLIC_API_URL`, `PUBLIC_SITE_URL` in `.env`). `make down` switches everything off and keeps it off.


| What | How it runs |
|---|---|
| **Code** | A tested snapshot in `~/.local/share/stock-news-pipeline/release` (`make release` runs lint + tests, builds the dashboard, then copies). The scheduled job and the services run the snapshot, so editing the working tree never breaks a run; `make deploy` again ships your changes. The copy waits for a running pipeline to finish. |
| **Hourly pipeline** | systemd user timer `stocknews-pipeline.timer`. `Persistent=true`: a run missed while the laptop slept happens as soon as it wakes. Replaces the old cron job. |
| **OmniRoute, API (:8080), dashboard (:3000)** | systemd user services: start at boot (lingering, set by `make up`), restart if they crash. |
| **Postgres** | Docker with `restart: unless-stopped`. |
| **Backups** | `stocknews-backup.timer`: a daily `pg_dump` (run inside the container) to `~/.local/share/stock-news-pipeline/backups`, newest 14 kept. `make restore FILE=…` takes a safety dump first. |
| **Alerts** | A desktop notification when a stage fails twice in a row, when it recovers, when a run crashes or the database is unreachable, and when a service or backup fails. Optionally `ALERT_WEBHOOK_URL` (e.g. an [ntfy.sh](https://ntfy.sh) topic for phone pushes) and `HEALTHCHECK_URL` (a dead-man's switch that notices when runs stop). |
| **Claude.ai login** | Scheduled runs never wait for a login: when the session expires, the report falls back to the next provider and the doctor tells you to `make claude-login`. |

Everyday commands: `make doctor` (checks everything, with fixes), `make status`, `make journal` (live service logs),
`make restart`, `make undeploy` (back to `make dev-up` style).

**Turning it off.** Shutting the laptop down stops everything; a run in progress ends cleanly and the next one picks up
where it left off. At the next boot it all comes back by itself, and the missed hourly run happens straight away. To
switch it off *and keep it off* across reboots: `make down` (`scripts/stop.sh`): it ends any run, stops the timers,
services and Postgres (data kept) and turns off start-at-boot. `make up` turns everything back on.

## Configuration

All settings live in `.env` (template: [.env.example](.env.example)); defaults are sensible.
The important ones:

| Variable | Purpose |
|---|---|
| `LOCAL_DB_URL` | Local Postgres (full dataset). |
| `NEON_DB_URL` | Neon connection with write access, used for sync. Empty = no sync. |
| `API_DB_URL` | What the API reads. **In production, a read-only Neon role.** |
| `FINNHUB_API_KEY` | Live quotes in the API. Without it, quotes fall back to the last daily close (`"stale": true`). |
| `OMNIROUTE_API_URL` | OmniRoute's *API Base* (`http://localhost:8000/v1`) — not the :20128 dashboard. |
| `OMNIROUTE_MODEL` | OmniRoute combo used for extraction. |
| `REPORT_PROVIDERS` | Report writer order, e.g. `anthropic,claude_web,omniroute`. |
| `ANTHROPIC_API_KEY` | Enables the `anthropic` report provider (default model `claude-opus-5`). |
| `CHROME_PROFILE_DIR` | Dedicated browser profile for the `claude_web` provider (`make claude-login` once). |
| `CORS_ORIGINS` | Allowed dashboard origins for the API, e.g. `https://tachyon-news.vercel.app,http://localhost:3000`. |
| `CORS_ORIGIN_REGEX` | Also allow origins matching this (e.g. every Vercel preview URL of the project). |
| `PUBLIC_API_URL` / `PUBLIC_SITE_URL` | The API as the hosted dashboard reaches it (the Tailscale Funnel URL) and the hosted dashboard; `make up` and `make doctor` check both from outside. |
| `AUTH_DB_URL` | Where accounts live (needs write access to `users` / `user_sessions`). Empty = the API's database. |
| `GOOGLE_CLIENT_ID` | Enables "Continue with Google" (an OAuth Web client ID; add the dashboard origin to its JavaScript origins). |
| `INDIA_FEEDS` | Indian market RSS feeds (defaults provided; empty turns India off). |
| `ALERT_WEBHOOK_URL` | Optional: alerts are also POSTed here as plain text (an ntfy.sh topic works). |
| `HEALTHCHECK_URL` | Optional dead-man's switch pinged after every scheduled run (`<url>` / `<url>/fail`). |

Tuning knobs (`EXTRACTION_MAX_PER_RUN`, `REPORT_REFRESH_NEW_ARTICLES`, `FETCH_SKIP_DOMAINS`, …) are
documented in [pipeline/config.py](pipeline/config.py).

## Operations

| Task | Command |
|---|---|
| Run everything once | `make run-pipeline` |
| Run some stages | `venv/bin/python -m pipeline.run_pipeline --only extract report` (or `--skip sync`) |
| Force a fresh report | `make run-report` (or `python -m pipeline.report.service --provider omniroute --force`) |
| Log in to Claude.ai for `claude_web` | `make claude-login` |
| Full Neon re-sync | `make sync-full` |
| Logs | `logs/pipeline.log` (rotated at 5 MB × 5), `logs/report.log`, `logs/backup.log`; services: `make journal` |
| Check everything | `make doctor` |
| Ship your changes to the scheduled job and services | `make deploy` |
| Back up / restore the local database | `make backup` · `make restore FILE=<dump>` |
| Everything on (installing it if needed) / off and kept off | `make up` · `make down` |

Safety properties:
- **No overlapping runs.** A file lock makes a run skip if the previous one is still going.
- **Stage isolation.** A failing stage is logged and the run exits non-zero, but later stages still run.
- **Self-migrating schema.** Every run applies idempotent `ADD COLUMN IF NOT EXISTS` upgrades
  ([pipeline/db/schema.py](pipeline/db/schema.py)) locally and on Neon before syncing.
- **Bounded work.** Fetch and extraction are capped per run, so a backlog drains over several runs.

### Report providers

| Provider | Needs | Notes |
|---|---|---|
| `anthropic` | `ANTHROPIC_API_KEY` | Most reliable; works unattended. Uses server-side refusal fallbacks. |
| `claude_web` | `make claude-login` once, a desktop session | Best-effort UI automation of Claude.ai; can break when the site changes. Skipped automatically without a display, and in scheduled runs once the login has expired. |
| `omniroute` | OmniRoute running | Free models; the always-available fallback. |

## Deployment

How it runs today: the pipeline, the API and the database live on the laptop (`make up`); the dashboard is a static
site on Vercel; the browser reaches the laptop's API over [Tailscale Funnel](https://tailscale.com/kb/1223/funnel)
(`tailscale funnel --bg 8080`, which `make up` opens), a public HTTPS address with no ports opened on the router.

**Dashboard → Vercel.** Project `stock-news`, domain `tachyon-news.vercel.app` (`stock-news-chi.vercel.app` redirects
to it). Deploy from the dashboard folder: `cd frontend/tachyon-news && npx vercel deploy --prod`. Set
`VITE_API_URL` to the Funnel URL in the project's environment variables and add the site to `CORS_ORIGINS`.

**API elsewhere (optional).** [render.yaml](render.yaml) deploys the API to Render instead: it installs only
[requirements-backend.txt](requirements-backend.txt) (no browser/pandas). Set `API_DB_URL` (read-only Neon role),
`FINNHUB_API_KEY` and `CORS_ORIGINS`. Health check: `GET /health` (503 when the database is unreachable).

The dashboard is a React + Vite app in `frontend/tachyon-news/`; on any static host:

| Setting | Value |
|---|---|
| Root directory | `frontend/tachyon-news` |
| Build command | `npm ci && npm run build` |
| Output directory | `dist` |
| Node | 22 |
| `VITE_API_URL` | The API's public URL. Read at **build** time, so rebuild after changing it. |

It uses hash routing, so no SPA rewrite rule is needed. Add the dashboard's origin to the API's `CORS_ORIGINS`.
Without a reachable API the dashboard runs on built-in demo data (`?demo=1` forces it; `?api=<url>` overrides the API).
Earlier dashboards are kept in `frontend/archive/` (`make dev-frontend-classic` serves v1 on :3001).

**Pipeline → your machine.** `make up` (see [Running it day to day](#running-it-day-to-day)). It needs the local Postgres, OmniRoute and (optionally) a desktop session.

## Accounts

The dashboard requires an account. Anyone can sign up with email + password (hashed with scrypt);
"Continue with Google" appears once `GOOGLE_CLIENT_ID` is set, and links to an existing account with the
same (Google-verified) email. Sessions are opaque bearer tokens — only their SHA-256 is stored — valid for
`AUTH_SESSION_DAYS`; signing out revokes them. Failed sign-ins are throttled per IP and per email.
`?demo=1` opens the built-in demo data without an account.

In production the API reads Neon through a read-only role, so give accounts their own role:

```sql
CREATE ROLE dashboard_auth LOGIN PASSWORD '…';
GRANT SELECT, INSERT, UPDATE, DELETE ON users, user_sessions TO dashboard_auth;
GRANT USAGE ON SEQUENCE users_id_seq TO dashboard_auth;
```

and set `AUTH_DB_URL` to that role's connection string.

## API

Interactive docs at `/docs`. Everything except `/health` and `/auth/*` needs `Authorization: Bearer <token>`. Responses for news/sectors/reports/candles are cacheable for 60 s.

| Endpoint | Description |
|---|---|
| `GET /health` | Pipeline freshness, last scrape, readiness %. Public. |
| `GET /auth/config` | Sign-in methods on offer. Public. |
| `POST /auth/signup`, `/auth/login`, `/auth/google`, `/auth/logout`; `GET /auth/me` | Accounts; sign-up/sign-in return `{token, user}`. |
| `GET /news` | Stories, newest first, with the `total` for the filters. Window: `since` / `until` (ISO), `hours` or `days`. Filters: `q` (headline, summary, source), `sentiment`, `event`, `sector`, `ticker`, `market` (`global` / `india`), `verified_only`, `status`, `trading_day`; `picks=true` for the top picks of the briefs in the window (by pick day, then rank); `ids=` for specific stories whatever the window. `page`, `limit≤200`. Each article carries `url`, `tickers`, `sector`, `market`, `verified` and `top_pick` (`{rank, why, trading_day}`). |
| `GET /summary` | Everything the dashboard shows about a window in one response: counts, sentiment, sectors, most discussed tickers (plus any `symbols=` asked for), a sentiment timeline (5-minute bars for an hour … weekly bars for years) and the number of top picks. Cached 60 s. |
| `GET /news/{id}` | One article with its full extraction. |
| `GET /news/{id}/reaction` | The priced-in meter: each ticker's move since the headline (with pre-market / after-hours for US listings) and beyond its benchmark, plus what similar stories were followed by, once there are ≥ 20 of them over ≥ 5 trading days. |
| `GET /sectors` | Sectors with news in the window, busiest first. |
| `GET /reports`, `/reports/latest`, `/reports/{YYYY-MM-DD}` | Daily briefs (Markdown) with their top picks. |
| `GET /quote/{symbol}`, `GET /quotes?symbols=A,B` | Live quote (Finnhub, cached 5 min) or last close, with its `currency` (null + `unit: "pts"` for indices). `?currency=USD|INR` converts at the stored daily rate; % change stays the listing's own. |
| `GET /candles/{symbol}?days=30&currency=native|USD|INR` | Stored daily closes (sparklines); converted closes use each day's own rate, and a chart is never mixed across currencies. |
| `GET /chart/{symbol}?span=1d|5d|1m|3m|6m|1y|5y&currency=…` | Price history for one chart span, fetched from Yahoo on demand and cached: 5-minute bars for 1D (US listings include pre-market and after-hours; `base` is the previous close), 15-minute for 5D, daily to 1Y, weekly for 5Y. Falls back to the stored closes (`source: "stored"`). |
| `GET /stats` | Article counts by status. |

## Development

```bash
make test        # unit + integration + e2e (uses a throwaway `stocknews_test` database)
make test-unit   # no database needed
make coverage
make lint

make dev-frontend     # dashboard with hot reload on :3000
make build-frontend   # production build → frontend/tachyon-news/dist
cd frontend/tachyon-news && npm run typecheck && npm run lint
```

Tests never touch the real databases or external services: the conftest points every engine at
test databases and blanks API keys; LLMs, Finviz, article sites and yfinance are faked.
The e2e tests drive all six stages through the real orchestrator, and drive the dashboard in headless
Chromium against a live API (skipped if the Playwright browser isn't installed). CI runs lint + tests on every push
([.github/workflows/ci.yml](.github/workflows/ci.yml)).

```
pipeline/
  run_pipeline.py      orchestrator (lock, stage selection, summary; --unattended for the timer)
  ops/                 alerts, backups, doctor
  config.py            typed settings        market_time.py   trading-day rules
  scraper/  fetch/  noise/  extract/  report/  prices/  sync/  db/
backend/               FastAPI app + routers (auth, health, news, reports, quotes); history.py (on-demand
                       price history), reaction.py (priced-in meter), fx.py (currency conversion)
frontend/tachyon-news/ dashboard: React 19 + TypeScript + Vite + Tailwind v4
frontend/archive/      previous dashboards (v1-classic, v2)
deploy/systemd/        user units installed by `make deploy` (timer, services, backups, failure notices)
scripts/               up.sh (make up), stop.sh (make down)
tests/                 unit / integration / e2e
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| Anything | `make doctor` first: it checks every dependency and prints the fix. |
| `M3 LLM extraction FAILED … OmniRoute unavailable` | `make up` (starts and waits for it), or `systemctl --user status stocknews-omniroute`; check `OMNIROUTE_API_URL` is the *API Base* it prints. |
| Report stage: `claude_web: no display` | No desktop session; the next provider is used. |
| Report stage: `not logged in` / `session expired` | `make claude-login`. |
| `browser profile … is in use` | `CHROME_PROFILE_DIR` must not be your everyday Chrome profile. |
| Sign-in says "Can't reach the server" | The laptop is off or asleep, or the tunnel is closed: `make up` (the page retries by itself once the API is back). `make doctor` checks the site and the tunnel from outside. |
| Dashboard shows demo data | API not running on :8080, `VITE_API_URL` wrong at build time, or `CORS_ORIGINS` excludes the dashboard's origin. |
| Dashboard stuck on loading skeletons locally | The API is reading Neon; set `API_DB_URL` to the local database. |
| Health `degraded` | No scrape in the last 3 hours: `systemctl --user list-timers 'stocknews-*'` and `journalctl --user -u stocknews-pipeline -e`. |
| A service keeps restarting | `journalctl --user -u stocknews-api -e` (or `-omniroute`, `-dashboard`). |

## License

Personal / non-commercial use only. Finviz scraping is for personal use; do not redistribute raw Finviz data.
Nothing here is investment advice.
