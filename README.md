# Stock-News Pipeline + Public Dashboard

A once-daily pipeline that:
1. Scrapes [Finviz news](https://finviz.com/news?v=3) via Playwright
2. Fetches article bodies with asyncio + httpx + trafilatura
3. Extracts structured insights via OmniRoute (free LLM combo)
4. Synthesises a daily market report via Claude.ai (Playwright automation)
5. Stores everything in local PostgreSQL, syncs a public subset to Neon
6. Exposes a FastAPI backend + Next.js frontend

---

## Quick Start

```bash
# 1. Clone and enter the repo
git clone <repo-url> stock-news-pipeline
cd stock-news-pipeline

# 2. Create venv + install deps + copy .env template
make setup

# 3. Edit .env — add your Neon URL, Finnhub key, etc.
nano .env

# 4. Start local Postgres
make db-up

# 5. Run migrations (create all tables on local + Neon)
make migrate

# 6. Run the full pipeline manually
make run-pipeline
```

---

## OmniRoute Setup (one-time)

```bash
npm i -g omniroute
omniroute   # starts at http://localhost:20128
# Open http://localhost:20128 → Add Gemini (Google AI Studio) key
# and/or Groq key → Create a combo named "extraction-combo"
```

---

## Scheduler

Install anacron daily job (runs on first boot Mon–Sat):

```bash
make setup-scheduler
```

---

## Backend (FastAPI)

```bash
make dev-backend        # local dev — http://localhost:8000/docs
```

Deploy to Render free: `Procfile` already configured.

---

## Tests

```bash
make test               # all tests + coverage report
make test-unit          # fast unit tests only
make test-integration   # integration tests (needs local DB)
make test-e2e           # full simulated pipeline run
```

---

## Milestones

| # | Status | Description |
|---|---|---|
| 0 | ✅ | Project skeleton, Docker Postgres, ORM models |
| 1 | ✅ | Finviz scraper + noise tagger |
| 2 | ✅ | Body fetch pipeline |
| 3 | ✅ | LLM extraction (OmniRoute) |
| 4 | ✅ | Daily report (Playwright → Claude.ai) |
| 5 | ✅ | Price data (Finnhub) |
| 6 | ✅ | Neon sync |
| 7 | ✅ | Orchestrator + anacron scheduler |
| 8 | ✅ | FastAPI backend (Render) |
| 9 | ⬜ | Frontend (Next.js / Vercel) |
| 10 | ✅ | Comprehensive test suite + README |

---

## License

Personal / non-commercial use only. Finviz scraping is personal use; do not redistribute raw Finviz data.
