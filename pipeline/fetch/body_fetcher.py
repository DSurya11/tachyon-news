"""
pipeline/fetch/body_fetcher.py
──────────────────────────────
Async body fetch loop — pulls article bodies for all articles with
status='new' or status='noise_tagged' (we fetch even noise-tagged articles
so the body is available for more accurate noise verification later).

Architecture (from implementation plan):
  GLOBAL_SEMAPHORE  = asyncio.Semaphore(20)   — total concurrent requests
  DOMAIN_SEMAPHORE  = defaultdict(Semaphore(3))— per-domain concurrency
  BATCH_SIZE        = 50
  TIMEOUT           = httpx.Timeout(10.0, connect=5.0)
  RETRIES           = 3
  BACKOFF_BASE      = 1.5 s + random jitter

- trafilatura runs in loop.run_in_executor() (CPU off event loop)
- asyncio.gather(..., return_exceptions=True) — one failure never aborts batch
- Per-domain circuit breaker (5 failures → open 5 min → half-open probe)
- Internal Finviz URLs: prepend https://finviz.com before fetching
- Updates articles.body, articles.status, scrape_runs.per_domain_stats
"""
from __future__ import annotations

import asyncio
import logging
import random
from collections import defaultdict
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from pipeline.db.local import LocalSession
from pipeline.db.models import Article, ScrapeRun
from pipeline.fetch.circuit_breaker import CircuitOpenError, registry as cb_registry
from pipeline.fetch.trafilatura_worker import extract as trafilatura_extract

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (from implementation plan)
# ---------------------------------------------------------------------------
GLOBAL_SEMAPHORE  = asyncio.Semaphore(20)
DOMAIN_SEMAPHORE: dict[str, asyncio.Semaphore] = defaultdict(lambda: asyncio.Semaphore(3))
BATCH_SIZE        = 50
TIMEOUT           = httpx.Timeout(10.0, connect=5.0)
RETRIES           = 3
BACKOFF_BASE      = 1.5   # seconds
FINVIZ_BASE       = "https://finviz.com"

# Statuses we will attempt to fetch bodies for
FETCHABLE_STATUSES = ("new", "noise_tagged")


# ---------------------------------------------------------------------------
# Per-article fetch with retries + circuit breaker
# ---------------------------------------------------------------------------

async def _fetch_one(
    client: httpx.AsyncClient,
    article_id: int,
    url: str,
) -> dict:
    """
    Fetch a single article URL, extract body with trafilatura.
    Returns a result dict that is applied to the DB regardless of outcome.
    """
    domain = urlparse(url).netloc.lower().lstrip("www.")
    cb = cb_registry.get(domain)

    # Circuit breaker — fail-fast if domain is open
    if not cb.allow_request():
        log.debug("[SKIP circuit-open] %s", url)
        return {
            "article_id": article_id,
            "body": None,
            "content_quality": "headline",
            "status": "body_fetched",
            "domain": domain,
            "success": False,
            "reason": "circuit_open",
        }

    last_exc: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            async with GLOBAL_SEMAPHORE:
                async with DOMAIN_SEMAPHORE[domain]:
                    resp = await client.get(url, timeout=TIMEOUT)
                    resp.raise_for_status()

            cb.record_success()
            body, quality = await trafilatura_extract(resp.text, url)

            return {
                "article_id": article_id,
                "body": body,
                "content_quality": quality,
                "status": "body_fetched",
                "domain": domain,
                "success": True,
                "reason": quality,
            }

        except (httpx.HTTPStatusError, httpx.RequestError, asyncio.TimeoutError) as exc:
            last_exc = exc
            cb.record_failure()
            if attempt < RETRIES:
                wait = BACKOFF_BASE ** attempt + random.uniform(0, 1.0)
                log.debug(
                    "[RETRY %d/%d] %s — %s — waiting %.1fs",
                    attempt, RETRIES, url, exc, wait,
                )
                await asyncio.sleep(wait)
            else:
                log.warning("[FAILED] %s — %s", url, exc)

    return {
        "article_id": article_id,
        "body": None,
        "content_quality": "headline",
        "status": "body_fetched",
        "domain": domain,
        "success": False,
        "reason": str(last_exc),
    }


# ---------------------------------------------------------------------------
# Batch runner
# ---------------------------------------------------------------------------

async def _run_batch(batch: list[tuple[int, str]]) -> list[dict]:
    """
    Concurrently fetch all (article_id, url) pairs in this batch.
    Uses asyncio.gather with return_exceptions=True so one failure
    never aborts the rest.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    }
    async with httpx.AsyncClient(
        follow_redirects=True,
        headers=headers,
        timeout=TIMEOUT,
    ) as client:
        tasks = [_fetch_one(client, aid, url) for aid, url in batch]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    results: list[dict] = []
    for i, r in enumerate(raw_results):
        if isinstance(r, Exception):
            aid, url = batch[i]
            log.error("[EXCEPTION] article %d %s — %s", aid, url, r)
            results.append({
                "article_id": aid,
                "body": None,
                "content_quality": "headline",
                "status": "body_fetched",
                "domain": urlparse(url).netloc.lower().lstrip("www."),
                "success": False,
                "reason": str(r),
            })
        else:
            results.append(r)
    return results


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _load_pending(limit: int | None = None) -> list[tuple[int, str]]:
    """Return (article_id, url) pairs that need body fetching."""
    with LocalSession() as session:
        q = (
            session.query(Article.id, Article.canonical_url)
            .filter(Article.status.in_(FETCHABLE_STATUSES))
            .filter(Article.body.is_(None))
        )
        if limit:
            q = q.limit(limit)
        return [(row[0], row[1]) for row in q.all()]


def _apply_results(results: list[dict], scrape_run_id: int | None) -> dict:
    """Write fetch results to DB. Returns per-domain stats dict."""
    domain_stats: dict[str, dict] = defaultdict(
        lambda: {"fetched": 0, "failed": 0, "full": 0, "snippet": 0, "headline": 0}
    )

    with LocalSession() as session:
        for r in results:
            article = session.get(Article, r["article_id"])
            if article is None:
                continue

            if r["body"]:
                article.body = r["body"]
            article.content_quality = r["content_quality"]

            # Status: if was noise_tagged keep that; otherwise set body_fetched
            if article.status not in ("noise_tagged",):
                article.status = r["status"]
            else:
                # noise-tagged articles get body stored but status unchanged
                # so the noise filter can use the body later
                article.status = "noise_tagged"

            d = r["domain"]
            if r["success"]:
                domain_stats[d]["fetched"] += 1
                domain_stats[d][r["content_quality"]] += 1
            else:
                domain_stats[d]["failed"] += 1

        # Update scrape_run per_domain_stats if provided
        if scrape_run_id is not None:
            run = session.get(ScrapeRun, scrape_run_id)
            if run:
                existing = dict(run.per_domain_stats or {})
                for domain, stats in domain_stats.items():
                    if domain in existing:
                        for k, v in stats.items():
                            existing[domain][k] = existing[domain].get(k, 0) + v
                    else:
                        existing[domain] = stats
                run.per_domain_stats = existing

        session.commit()

    return dict(domain_stats)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def run_body_fetch(
    scrape_run_id: int | None = None,
    limit: int | None = None,
) -> dict:
    """
    Fetch bodies for all pending articles in batches of BATCH_SIZE.

    Args:
        scrape_run_id: Optional ScrapeRun to update per_domain_stats on.
        limit:         Cap total articles processed (useful for testing).

    Returns:
        Aggregated per-domain stats dict.
    """
    pending = _load_pending(limit=limit)
    log.info("Body fetcher: %d articles to fetch", len(pending))

    if not pending:
        log.info("No pending articles — nothing to fetch.")
        return {}

    # Resolve internal Finviz URLs
    resolved: list[tuple[int, str]] = []
    for aid, url in pending:
        if url.startswith("/"):
            url = FINVIZ_BASE + url
        resolved.append((aid, url))

    all_stats: dict[str, dict] = defaultdict(
        lambda: {"fetched": 0, "failed": 0, "full": 0, "snippet": 0, "headline": 0}
    )

    # Process in batches
    for i in range(0, len(resolved), BATCH_SIZE):
        batch = resolved[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(resolved) + BATCH_SIZE - 1) // BATCH_SIZE
        log.info("Batch %d/%d (%d articles)…", batch_num, total_batches, len(batch))

        results = await _run_batch(batch)
        batch_stats = _apply_results(results, scrape_run_id)

        # Merge into aggregate
        for domain, stats in batch_stats.items():
            for k, v in stats.items():
                all_stats[domain][k] = all_stats[domain].get(k, 0) + v

        # Summary for this batch
        fetched = sum(1 for r in results if r["success"])
        full    = sum(1 for r in results if r["content_quality"] == "full")
        log.info(
            "Batch %d done: %d/%d fetched, %d full",
            batch_num, fetched, len(batch), full,
        )

    return dict(all_stats)


def fetch_bodies(scrape_run_id: int | None = None, limit: int | None = None) -> dict:
    """Synchronous wrapper — called by the pipeline orchestrator."""
    return asyncio.run(run_body_fetch(scrape_run_id=scrape_run_id, limit=limit))
