"""
pipeline/fetch/trafilatura_worker.py
─────────────────────────────────────
Runs trafilatura content extraction in a thread-pool executor so CPU-bound
HTML parsing doesn't block the asyncio event loop.

Quality ladder (returned as content_quality string):
  "full"     — trafilatura extracted a meaningful body (≥100 chars)
  "snippet"  — trafilatura returned something but it's short (<100 chars)
  "headline" — trafilatura returned nothing; caller should use headline only
"""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

import trafilatura

log = logging.getLogger(__name__)

# Shared thread pool — sized to not overwhelm the CPU;
# trafilatura is lxml-based so 4-8 threads is plenty.
_EXECUTOR = ThreadPoolExecutor(max_workers=6, thread_name_prefix="trafilatura")

FULL_MIN_CHARS = 100   # minimum chars to count as "full"


def _extract_sync(html: str, url: str) -> tuple[str | None, str]:
    """
    Run trafilatura extraction synchronously (called in executor thread).
    Returns (body_text, content_quality).
    """
    try:
        text = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=True,
            no_fallback=False,          # try readability fallback
            favor_precision=False,      # prefer recall for news articles
            deduplicate=True,
        )
        if text and len(text.strip()) >= FULL_MIN_CHARS:
            return text.strip(), "full"
        elif text and text.strip():
            return text.strip(), "snippet"
        else:
            return None, "headline"
    except Exception as exc:  # noqa: BLE001 — a parser crash must not fail the batch
        log.debug("trafilatura extraction error for %s: %s", url, exc)
        return None, "headline"


async def extract(html: str, url: str) -> tuple[str | None, str]:
    """
    Async wrapper: run trafilatura in the thread pool executor.
    Returns (body_text, content_quality).
    """
    loop = asyncio.get_running_loop()
    body, quality = await loop.run_in_executor(_EXECUTOR, _extract_sync, html, url)
    log.debug("trafilatura [%s] %s → %d chars", quality, url, len(body) if body else 0)
    return body, quality
