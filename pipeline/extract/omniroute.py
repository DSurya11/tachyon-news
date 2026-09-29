"""
pipeline/extract/omniroute.py
──────────────────────────────
LLM extraction worker using the OpenAI-compatible API exposed by OmniRoute.

A few worker threads (EXTRACTION_CONCURRENCY) run this loop in parallel.
Flow per article (one short transaction each):
  1. Claim the newest eligible article with FOR UPDATE SKIP LOCKED.
     Eligible = status 'body_fetched', or 'extraction_failed' with fewer
     than EXTRACTION_MAX_ATTEMPTS attempts (retried on later runs).
  2. Call the model (JSON mode when the router supports it), parse and
     normalise the JSON, validate, verify grounding against the body.
  3. Save → 'verified' / 'extracted', or count the attempt → 'extraction_failed'.

Outages are not the article's fault: connection errors, timeouts, 429 and
5xx leave the article untouched, and after EXTRACTION_MAX_CONSECUTIVE_ERRORS
of them in a row the stage stops and reports failure.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from openai import APIConnectionError, APIStatusError, APITimeoutError, BadRequestError, OpenAI
from sqlalchemy import text

from pipeline.config import settings
from pipeline.db.local import LocalSession
from pipeline.db.models import Article, Extraction
from pipeline.extract.prompt import (
    REQUIRED_FIELDS,
    SYSTEM_PROMPT,
    build_user_prompt,
    normalize_extraction,
    validate_extraction,
)
from pipeline.extract.verifier import verify

log = logging.getLogger(__name__)

MAX_TOKENS = 4096
PARSE_RETRY_REMINDER = (
    "Your previous reply was not a complete JSON object. Reply again with ONLY the "
    "JSON object described in the instructions — no reasoning, no markdown."
)


class LLMUnavailableError(RuntimeError):
    """The router is unreachable or overloaded — not the article's fault."""


def make_client() -> OpenAI:
    return OpenAI(
        base_url=settings.omniroute_api_url,
        api_key=settings.omniroute_api_key or "unused",
        timeout=settings.omniroute_timeout_s,
        max_retries=1,
    )


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

_THINK_RE = re.compile(r"<think(?:ing)?>.*?</think(?:ing)?>", re.DOTALL | re.IGNORECASE)
_DECODER = json.JSONDecoder()


def _content_to_text(content: str | list | None) -> str:
    if content is None:
        return ""
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text", "")))
            else:
                parts.append(str(getattr(block, "text", block)))
        return "".join(parts)
    return str(content)


def parse_llm_response(content: str | list | None) -> dict | None:
    """
    Extract the extraction object from a model reply.

    Handles bare JSON, ```json fences, <think> blocks and reasoning prose
    around the object.  Scans every '{' and keeps the candidate object that
    contains the most required keys (ties → the later one, since models tend
    to "think" first and answer last).
    """
    raw = _THINK_RE.sub("", _content_to_text(content)).strip()
    if not raw:
        return None

    best: dict | None = None
    best_score = 0
    idx = raw.find("{")
    while idx != -1:
        try:
            obj, _end = _DECODER.raw_decode(raw, idx)
        except json.JSONDecodeError:
            obj = None
        if isinstance(obj, dict):
            score = len(REQUIRED_FIELDS & obj.keys())
            if score and score >= best_score:
                best, best_score = obj, score
        idx = raw.find("{", idx + 1)

    if best is None:
        log.debug("Could not parse LLM response as JSON: %r", raw[:200])
    return best


# ---------------------------------------------------------------------------
# Model call
# ---------------------------------------------------------------------------

@dataclass
class _CallState:
    json_mode: bool = field(default_factory=lambda: settings.omniroute_json_mode)


def _complete(client: OpenAI, state: _CallState, messages: list[dict]) -> tuple[str, str, str | None]:
    """One chat completion. Returns (text, model_used, finish_reason)."""
    kwargs: dict = {
        "model": settings.omniroute_model,
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": MAX_TOKENS,
    }
    if state.json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    try:
        resp = client.chat.completions.create(**kwargs)
    except BadRequestError as exc:
        if state.json_mode and "response_format" in str(exc).lower():
            log.warning("Router rejected response_format — disabling JSON mode for this run.")
            state.json_mode = False
            return _complete(client, state, messages)
        raise
    except (APIConnectionError, APITimeoutError) as exc:
        raise LLMUnavailableError(f"connection: {exc}") from exc
    except APIStatusError as exc:
        if exc.status_code == 429 or exc.status_code >= 500:
            raise LLMUnavailableError(f"HTTP {exc.status_code}: {exc.message}") from exc
        raise

    if not resp.choices:
        return "", resp.model or settings.omniroute_model, None
    choice = resp.choices[0]
    return (
        _content_to_text(choice.message.content),
        resp.model or settings.omniroute_model,
        choice.finish_reason,
    )


def extract_article(client: OpenAI, state: _CallState, headline: str, body: str | None) -> tuple[dict | None, str]:
    """
    Extract one article. Returns (normalised_data | None, detail).
    Retries once with a corrective reminder when the reply is not usable JSON.
    Raises LLMUnavailableError on outages.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(headline, body, settings.extraction_max_body_chars)},
    ]
    detail = "no_response"
    for attempt in (1, 2):
        content, model_used, finish_reason = _complete(client, state, messages)
        raw = parse_llm_response(content)
        if raw is not None:
            data = normalize_extraction(raw)
            errors = validate_extraction(data)
            if not errors:
                data["_model_used"] = model_used
                return data, "ok"
            detail = "invalid: " + "; ".join(errors)
        else:
            detail = f"unparseable (finish_reason={finish_reason}): {content[:120]!r}"
        if attempt == 1:
            messages = [*messages, {"role": "assistant", "content": content[:2000] or "(empty)"},
                        {"role": "user", "content": PARSE_RETRY_REMINDER}]
    return None, detail


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------

_CLAIM_SQL = text(
    """
    SELECT id FROM articles
    WHERE (status = 'body_fetched'
           OR (status = 'extraction_failed' AND extraction_attempts < :max_attempts))
      AND NOT (id = ANY(:tried))
    ORDER BY (status = 'body_fetched') DESC, published_at DESC NULLS LAST, id DESC
    LIMIT 1
    FOR UPDATE SKIP LOCKED
    """
)


def _claim_next(session, tried: list[int]) -> Article | None:
    row = session.execute(
        _CLAIM_SQL, {"max_attempts": settings.extraction_max_attempts, "tried": tried}
    ).first()
    return session.get(Article, row[0]) if row else None


def _save_extraction(session, article: Article, data: dict, verified: bool) -> None:
    session.add(
        Extraction(
            article_id=article.id,
            tickers=data["tickers"],
            event_type=data["event_type"],
            sentiment=data["sentiment"],
            key_facts=data["key_facts"],
            numbers=data["numbers"],
            one_line=data["one_line"],
            evidence=data["evidence"],
            sector=data.get("sector"),
            model_used=data.get("_model_used") or settings.omniroute_model,
        )
    )
    article.status = "verified" if verified else "extracted"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

@dataclass
class _RunState:
    """Shared between worker threads; every mutation happens under `lock`."""

    limit: int
    lock: threading.Lock = field(default_factory=threading.Lock)
    reserved: int = 0  # slots handed out, so concurrent workers can't overshoot `limit`
    tried: list[int] = field(default_factory=list)
    stats: dict = field(
        default_factory=lambda: {"extracted": 0, "verified": 0, "failed": 0, "skipped": 0, "aborted": False}
    )
    consecutive_errors: int = 0
    last_outage: LLMUnavailableError | None = None

    def count(self, key: str, n: int = 1) -> None:
        with self.lock:
            self.stats[key] += n


def _process_next(client: OpenAI, call_state: _CallState, run: _RunState) -> bool:
    """Claim and process one article. Returns False when the worker should stop."""
    with run.lock:
        if run.stats["aborted"] or run.reserved >= run.limit:
            return False
        run.reserved += 1
        tried = list(run.tried)

    with LocalSession() as session:
        # SKIP LOCKED keeps concurrent workers off each other's rows.
        article = _claim_next(session, tried)
        if article is None:
            with run.lock:
                run.reserved -= 1
            return False
        with run.lock:
            run.tried.append(article.id)

        if session.query(Extraction.id).filter(Extraction.article_id == article.id).first():
            # Defensive: an extraction exists but the status was never advanced.
            article.status = "extracted"
            session.commit()
            run.count("skipped")
            return True

        t0 = time.monotonic()
        try:
            data, detail = extract_article(client, call_state, article.headline, article.body)
        except LLMUnavailableError as exc:
            session.rollback()
            with run.lock:
                run.consecutive_errors += 1
                run.last_outage = exc
                errors = run.consecutive_errors
                if errors >= settings.extraction_max_consecutive_errors:
                    run.stats["aborted"] = True
            log.warning("OmniRoute unavailable (%d in a row): %s", errors, exc)
            with run.lock:
                run.reserved -= 1  # the article was not processed; give the slot back
            if errors >= settings.extraction_max_consecutive_errors:
                log.error("Aborting extraction: OmniRoute is unavailable.")
                return False
            time.sleep(min(2**errors, 30))
            return True
        except APIStatusError as exc:
            # Non-retryable 4xx for this specific request — count it against the article.
            data, detail = None, f"HTTP {exc.status_code}: {exc.message}"

        with run.lock:
            run.consecutive_errors = 0
        elapsed = time.monotonic() - t0
        article.extraction_attempts = (article.extraction_attempts or 0) + 1

        if data is None:
            article.status = "extraction_failed"
            run.count("failed")
            log.warning(
                "Article %d extraction failed (attempt %d/%d): %s",
                article.id, article.extraction_attempts, settings.extraction_max_attempts, detail,
            )
        else:
            result = verify(body=article.body, evidence=data["evidence"], numbers=data["numbers"])
            _save_extraction(session, article, data, result.passed)
            run.count("extracted")
            run.count("verified", int(result.passed))
            log.info("Article %d → %s in %.1fs (%s)", article.id, article.status, elapsed, result.note)

        session.commit()
    return True


def _worker(client: OpenAI, call_state: _CallState, run: _RunState) -> None:
    while _process_next(client, call_state, run):
        pass


def run_extraction(max_articles: int | None = None, concurrency: int | None = None) -> dict:
    """
    Extract structured data from pending articles with a small pool of workers.
    Returns stats {extracted, verified, failed, skipped, aborted}.
    Raises LLMUnavailableError if the router was unusable and nothing succeeded.
    """
    run = _RunState(limit=max_articles or settings.extraction_max_per_run)
    client = make_client()
    call_state = _CallState()
    workers = max(1, concurrency or settings.extraction_concurrency)

    if workers == 1:
        _worker(client, call_state, run)
    else:
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="extract") as pool:
            for future in [pool.submit(_worker, client, call_state, run) for _ in range(workers)]:
                future.result()  # re-raise unexpected worker errors

    stats = run.stats
    log.info(
        "Extraction complete: extracted=%d verified=%d failed=%d skipped=%d%s",
        stats["extracted"], stats["verified"], stats["failed"], stats["skipped"],
        " (ABORTED: router unavailable)" if stats["aborted"] else "",
    )
    if stats["aborted"] and stats["extracted"] == 0:
        raise LLMUnavailableError(f"OmniRoute unavailable at {settings.omniroute_api_url}: {run.last_outage}")
    return stats
