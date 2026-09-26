"""
pipeline/extract/omniroute.py
──────────────────────────────
OmniRoute LLM extraction worker.

Uses an OpenAI-compatible client pointed at the local OmniRoute server
(http://localhost:20128/v1).  Model is set to the configured combo name
(default: "extraction-combo").

Worker pattern:
  - Claims rows with SELECT ... FOR UPDATE SKIP LOCKED (via raw SQL)
  - Processes articles with status='body_fetched'
  - On success:  inserts into extractions, updates article.status → 'extracted'
                 then immediately runs verifier → 'verified' if passes
  - On LLM error: logs and leaves article.status unchanged for retry

Setup (one-time, done manually):
  npm i -g omniroute && omniroute
  Open http://localhost:20128 → add Gemini/Groq key → create combo "extraction-combo"
"""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone

from openai import OpenAI, APIConnectionError, APIStatusError

from pipeline.config import settings
from pipeline.db.local import LocalSession
from pipeline.db.models import Article, Extraction
from pipeline.extract.prompt import (
    SYSTEM_PROMPT,
    build_user_prompt,
    validate_extraction,
)
from pipeline.extract.verifier import verify

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OmniRoute client (OpenAI-compat)
# ---------------------------------------------------------------------------

def _make_client() -> OpenAI:
    # Use port 8000 which is the actual inference API plane, and the explicit key we set
    base_url = settings.omniroute_base_url.replace("20128", "8000")
    return OpenAI(
        base_url=base_url,
        api_key="my-secret-key",
        timeout=60.0,
        max_retries=0,
    )


# ---------------------------------------------------------------------------
# JSON extraction from LLM response
# ---------------------------------------------------------------------------

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


def _parse_llm_response(content: str | list | None) -> dict | None:
    """
    Parse the LLM response into a dict.
    Handles:
      - Raw JSON object
      - JSON wrapped in ```json ... ``` fences
      - Content block array format
    Returns None on failure.
    """
    if not content:
        return None
        
    if isinstance(content, list):
        full_text = []
        for block in content:
            if hasattr(block, "text"):
                full_text.append(block.text)
            elif isinstance(block, dict) and "text" in block:
                full_text.append(block["text"])
            else:
                full_text.append(str(block))
        content = "".join(full_text)
            
    if not isinstance(content, str):
        content = str(content)

    content = content.strip()

    # Try raw JSON first
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Try stripping markdown fences
    m = _JSON_BLOCK_RE.search(content)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # Last attempt: find first { ... } block
    start = content.find("{")
    end   = content.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(content[start : end + 1])
        except json.JSONDecodeError:
            pass

    log.warning("Could not parse LLM response as JSON: %r", content[:200])
    return None


# ---------------------------------------------------------------------------
# Single article extraction
# ---------------------------------------------------------------------------

def _extract_article(client: OpenAI, article: Article) -> dict | None:
    """
    Call OmniRoute with the article's headline + body.
    Returns the parsed extraction dict, or None on failure.
    """
    user_msg = build_user_prompt(article.headline, article.body)

    try:
        response = client.chat.completions.create(
            model=settings.omniroute_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_msg},
            ],
            temperature=0.0,      # deterministic — we want facts, not creativity
            max_tokens=4096,
        )
    except APIConnectionError as exc:
        log.error("OmniRoute connection error: %s", exc)
        return None
    except APIStatusError as exc:
        log.error("OmniRoute API error %s: %s", exc.status_code, exc.message)
        return None

    content      = response.choices[0].message.content or ""
    model_used   = response.model or settings.omniroute_model

    data = _parse_llm_response(content)
    if data is None:
        return None

    data["_model_used"] = model_used
    return data


# ---------------------------------------------------------------------------
# DB: claim + process batch
# ---------------------------------------------------------------------------

def _claim_batch(session, batch_size: int) -> list[Article]:
    """
    Claim up to batch_size articles using SELECT FOR UPDATE SKIP LOCKED.
    This prevents concurrent workers from processing the same article.
    """
    from sqlalchemy import text

    # Raw SQL for FOR UPDATE SKIP LOCKED (SQLAlchemy ORM doesn't expose SKIP LOCKED cleanly)
    result = session.execute(
        text("""
            SELECT id FROM articles
            WHERE status = 'body_fetched'
            LIMIT :limit
            FOR UPDATE SKIP LOCKED
        """),
        {"limit": batch_size},
    )
    ids = [row[0] for row in result]
    if not ids:
        return []
    return session.query(Article).filter(Article.id.in_(ids)).all()


def _save_extraction(
    session,
    article: Article,
    data: dict,
    verified: bool,
) -> None:
    """Persist extraction to DB and update article status."""
    ext = Extraction(
        article_id  = article.id,
        tickers     = data.get("tickers") or [],
        event_type  = data.get("event_type") or "other",
        sentiment   = data.get("sentiment") or "neutral",
        key_facts   = data.get("key_facts") or [],
        numbers     = data.get("numbers") or [],
        one_line    = data.get("one_line") or "",
        evidence    = data.get("evidence") or "",
        model_used  = data.get("_model_used") or settings.omniroute_model,
        created_at  = datetime.now(timezone.utc),
    )
    session.add(ext)

    article.status = "verified" if verified else "extracted"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_extraction(batch_size: int = 5, max_articles: int | None = None) -> dict:
    """
    Extract structured data from all body_fetched articles.

    Args:
        batch_size:   Articles per DB transaction (FOR UPDATE SKIP LOCKED).
        max_articles: Cap total articles processed (useful for testing).

    Returns:
        Stats dict: {extracted, verified, failed, skipped}.
    """
    client = _make_client()
    stats  = {"extracted": 0, "verified": 0, "failed": 0, "skipped": 0}
    total_processed = 0

    while True:
        if max_articles and total_processed >= max_articles:
            break

        effective_batch = batch_size
        if max_articles:
            effective_batch = min(batch_size, max_articles - total_processed)

        with LocalSession() as session:
            articles = _claim_batch(session, effective_batch)
            if not articles:
                log.info("No more body_fetched articles to extract.")
                break

            log.info("Extraction batch: %d articles", len(articles))

            for article in articles:
                # Skip if already has an extraction (safety check)
                existing_ext = (
                    session.query(Extraction)
                    .filter(Extraction.article_id == article.id)
                    .first()
                )
                if existing_ext:
                    log.debug("Article %d already has extraction — skipping", article.id)
                    stats["skipped"] += 1
                    continue

                t0 = time.monotonic()
                data = _extract_article(client, article)
                elapsed = time.monotonic() - t0

                if data is None:
                    log.warning("Extraction failed for article %d", article.id)
                    stats["failed"] += 1
                    article.status = 'extraction_failed'
                    continue

                # Validate required fields
                errors = validate_extraction(data)
                if errors:
                    log.warning(
                        "Extraction invalid for article %d: %s", article.id, errors
                    )
                    stats["failed"] += 1
                    article.status = 'extraction_failed'
                    continue

                # Verify evidence + numbers against body
                verify_result = verify(
                    body     = article.body,
                    evidence = data.get("evidence"),
                    numbers  = data.get("numbers"),
                )
                verified = verify_result.passed

                _save_extraction(session, article, data, verified)

                if verified:
                    stats["verified"] += 1
                stats["extracted"] += 1

                log.info(
                    "Article %d extracted in %.1fs → %s | verify=%s",
                    article.id,
                    elapsed,
                    article.status,
                    verify_result.note,
                )

            session.commit()
            total_processed += len(articles)

        # Small delay between batches to be polite to free-tier OmniRoute
        if len(articles) == effective_batch:
            time.sleep(0.5)

    log.info(
        "Extraction complete: extracted=%d verified=%d failed=%d skipped=%d",
        stats["extracted"], stats["verified"], stats["failed"], stats["skipped"],
    )
    return stats
