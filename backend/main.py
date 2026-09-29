"""
backend/main.py
───────────────
API for the dashboard. Every data endpoint requires a signed-in user
(`Authorization: Bearer <token>` from /auth/*); /health stays public for uptime checks.

    uvicorn backend.main:app --port 8080       # docs at /docs
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from backend.auth import current_user
from backend.db import auth_engine
from backend.routers import auth, health, news, quotes, reports
from pipeline.config import settings
from pipeline.db.models import User, UserSession

log = logging.getLogger(__name__)

API_VERSION = "1.0.0"
# Data changes at most hourly; let the browser reuse responses briefly.
# Responses are per-user now, so they are `private` (never stored by shared caches).
CACHEABLE_PREFIXES = ("/news", "/sectors", "/reports", "/candles")
CACHE_SECONDS = 60
# JSON-only API: nothing should sniff, frame or leak referrers from its responses.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=3.0))
    try:  # accounts tables (the pipeline's migrate also creates them)
        User.metadata.create_all(auth_engine, tables=[User.__table__, UserSession.__table__])
    except Exception as exc:  # noqa: BLE001 — e.g. a role without CREATE; tables may already exist
        log.warning("Could not ensure account tables: %s", exc)
    try:
        yield
    finally:
        await app.state.http.aclose()


app = FastAPI(
    title="Stock-News Pipeline API",
    description="Sector-grouped market news with LLM extractions, daily reports and quotes.",
    version=API_VERSION,
    lifespan=lifespan,
)

origins = settings.cors_origin_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    # A hosted dashboard is served from several addresses (Vercel: the project alias plus one
    # per deployment), so a pattern can allow them all without allowing any other site.
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=False,  # bearer tokens, not cookies
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.middleware("http")
async def cache_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    if (
        request.method == "GET"
        and response.status_code == 200
        and request.url.path.startswith(CACHEABLE_PREFIXES)
        and "cache-control" not in response.headers
    ):
        response.headers["Cache-Control"] = f"private, max-age={CACHE_SECONDS}"
        response.headers["Vary"] = "Authorization"
    return response


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {"name": app.title, "version": API_VERSION, "docs": "/docs", "health": "/health"}


signed_in = [Depends(current_user)]
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(news.router, dependencies=signed_in)
app.include_router(reports.router, dependencies=signed_in)
app.include_router(quotes.router, dependencies=signed_in)
