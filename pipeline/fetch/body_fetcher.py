"""
pipeline/fetch/body_fetcher.py
──────────────────────────────
Async body fetch loop for articles with status='new'.

  - Global concurrency 20, per-domain concurrency 3 (semaphores are created
    per run so they are bound to the running event loop)
  - Batches of 50, newest articles first, capped by FETCH_MAX_PER_RUN
  - Retries only transient failures (network errors, 408/429/5xx) with
    exponential backoff + jitter; a 403/404 is final on the first attempt
  - Per-domain circuit breaker (5 failures → open 5 min → half-open probe)
  - Hard-paywall domains (FETCH_SKIP_DOMAINS) are never requested
  - trafilatura runs in a thread pool so parsing never blocks the loop
  - Writes articles.body / content_quality / status and the scrape run's
    per_domain_stats

Noise-tagged articles are not fetched: they are never extracted, so the
request would be wasted (and most of them are wire-service boilerplate).
"""
from __future__ import annotations

import asyncio
import logging
import random
from collections import defaultdict
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx
from sqlalchemy import func, select

from pipeline.config import settings
from pipeline.db.local import LocalSession
from pipeline.db.models import Article, ScrapeRun
from pipeline.fetch.circuit_breaker import registry as cb_registry
from pipeline.fetch.trafilatura_worker import extract as trafilatura_extract

log = logging.getLogger(__name__)

GLOBAL_CONCURRENCY = 20
DOMAIN_CONCURRENCY = 3
# Minimum gap between request starts to one domain. Bursts (e.g. a first pass over
# ~90 Economic Times links) trip publishers' bot protection into 403s.
DOMAIN_MIN_INTERVAL_S = 0.75
BATCH_SIZE = 50
TIMEOUT = httpx.Timeout(10.0, connect=5.0)
RETRIES = 3
BACKOFF_BASE = 1.5  # seconds
FINVIZ_BASE = "https://finviz.com"
RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
}


def domain_of(url: str) -> str:
    """Registrable-ish host used for rate limiting and stats ('www.' stripped)."""
    return urlparse(url).netloc.lower().removeprefix("www.")


def is_skipped_domain(domain: str, skip: frozenset[str]) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in skip)


@dataclass
class FetchResult:
    article_id: int
    domain: str
    body: str | None = None
    content_quality: str = "headline"
    success: bool = False
    reason: str = ""


@dataclass
class _Limits:
    global_sem: asyncio.Semaphore = field(default_factory=lambda: asyncio.Semaphore(GLOBAL_CONCURRENCY))
    domain_sems: dict[str, asyncio.Semaphore] = field(
        default_factory=lambda: defaultdict(lambda: asyncio.Semaphore(DOMAIN_CONCURRENCY))
    )
    domain_next: dict[str, float] = field(default_factory=dict)

    async def pace(self, domain: str) -> None:
        """Reserve the next start slot for `domain`, sleeping until it arrives."""
        loop = asyncio.get_running_loop()
        now = loop.time()
        slot = max(now, self.domain_next.get(domain, now))
        self.domain_next[domain] = slot + DOMAIN_MIN_INTERVAL_S
        if slot > now:
            await asyncio.sleep(slot - now)


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS
    return isinstance(exc, httpx.RequestError | asyncio.TimeoutError)


async def _fetch_one(client: httpx.AsyncClient, limits: _Limits, article_id: int, url: str) -> FetchResult:
    domain = domain_of(url)
    result = FetchResult(article_id=article_id, domain=domain)

    if is_skipped_domain(domain, settings.fetch_skip_domain_set):
        result.reason = "skipped_paywall"
        return result

    cb = cb_registry.get(domain)
    if not cb.allow_request():
        result.reason = "circuit_open"
        return result

    for attempt in range(1, RETRIES + 1):
        if attempt > 1 and not cb.allow_request():
            result.reason = "circuit_open"
            return result
        try:
            async with limits.domain_sems[domain]:
                await limits.pace(domain)
                async with limits.global_sem:
                    resp = await client.get(url, timeout=TIMEOUT)
                resp.raise_for_status()
        except (TimeoutError, httpx.HTTPError) as exc:
            cb.record_failure()
            result.reason = str(exc)[:200]
            if attempt < RETRIES and _is_retryable(exc):
                await asyncio.sleep(BACKOFF_BASE**attempt + random.uniform(0, 1.0))
                continue
            log.info("[fetch failed] %s — %s", url, result.reason)
            return result

        cb.record_success()
        result.body, result.content_quality = await trafilatura_extract(resp.text, url)
        result.success = True
        result.reason = result.content_quality
        return result

    return result


async def _run_batch(client: httpx.AsyncClient, limits: _Limits, batch: list[tuple[int, str]]) -> list[FetchResult]:
    raw = await asyncio.gather(
        *(_fetch_one(client, limits, aid, url) for aid, url in batch),
        return_exceptions=True,
    )
    results: list[FetchResult] = []
    for (aid, url), r in zip(batch, raw, strict=True):
        if isinstance(r, BaseException):
            log.error("[fetch exception] article %d %s — %r", aid, url, r)
            results.append(FetchResult(article_id=aid, domain=domain_of(url), reason=repr(r)[:200]))
        else:
            results.append(r)
    return results


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _resolve_url(url: str) -> str:
    return FINVIZ_BASE + url if url.startswith("/") else url



def _load_pending(limit: int) -> list[tuple[int, str]]:
    """(article_id, url) pairs that still need a body, newest first."""
    with LocalSession() as session:
        rows = session.execute(
            select(Article.id, func.coalesce(Article.url, Article.canonical_url))
            .where(Article.status == "new", Article.body.is_(None))
            .order_by(Article.published_at.desc().nulls_last(), Article.id.desc())
            .limit(limit)
        ).all()
    return [(aid, _resolve_url(url)) for aid, url in rows]


def _empty_stats() -> dict[str, int]:
    return {"fetched": 0, "failed": 0, "skipped": 0, "full": 0, "snippet": 0, "headline": 0}


def _apply_results(results: list[FetchResult], scrape_run_id: int | None) -> dict[str, dict[str, int]]:
    """Write fetch results to the DB. Returns per-domain stats for this batch."""
    domain_stats: dict[str, dict[str, int]] = defaultdict(_empty_stats)

    with LocalSession() as session:
        for r in results:
            article = session.get(Article, r.article_id)
            if article is None or article.status != "new":
                continue
            if r.body:
                article.body = r.body
            article.content_quality = r.content_quality
            article.status = "body_fetched"  # headline-only articles are still extracted

            stats = domain_stats[r.domain]
            if r.success:
                stats["fetched"] += 1
                stats[r.content_quality] += 1
            elif r.reason in ("skipped_paywall", "circuit_open"):
                stats["skipped"] += 1
            else:
                stats["failed"] += 1

        if scrape_run_id is not None and domain_stats:
            run = session.get(ScrapeRun, scrape_run_id)
            if run is not None:
                merged = {d: dict(v) for d, v in (run.per_domain_stats or {}).items()}
                for domain, stats in domain_stats.items():
                    bucket = merged.setdefault(domain, {})
                    for k, v in stats.items():
                        bucket[k] = bucket.get(k, 0) + v
                run.per_domain_stats = merged  # reassign so SQLAlchemy sees the change

        session.commit()

    return dict(domain_stats)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def run_body_fetch(scrape_run_id: int | None = None, limit: int | None = None) -> dict:
    """Fetch bodies for pending articles. Returns aggregated per-domain stats."""
    pending = _load_pending(limit or settings.fetch_max_per_run)
    log.info("Body fetcher: %d articles to fetch", len(pending))
    if not pending:
        return {}

    limits = _Limits()
    all_stats: dict[str, dict[str, int]] = defaultdict(_empty_stats)

    async with httpx.AsyncClient(follow_redirects=True, headers=HEADERS, timeout=TIMEOUT) as client:
        total_batches = (len(pending) + BATCH_SIZE - 1) // BATCH_SIZE
        for batch_num, start in enumerate(range(0, len(pending), BATCH_SIZE), start=1):
            batch = pending[start : start + BATCH_SIZE]
            results = await _run_batch(client, limits, batch)
            for domain, stats in _apply_results(results, scrape_run_id).items():
                for k, v in stats.items():
                    all_stats[domain][k] += v
            log.info(
                "Batch %d/%d: %d/%d fetched, %d full",
                batch_num,
                total_batches,
                sum(r.success for r in results),
                len(batch),
                sum(r.content_quality == "full" for r in results),
            )

    return dict(all_stats)


def fetch_bodies(scrape_run_id: int | None = None, limit: int | None = None) -> dict:
    """Synchronous wrapper — called by the pipeline orchestrator."""
    return asyncio.run(run_body_fetch(scrape_run_id=scrape_run_id, limit=limit))
