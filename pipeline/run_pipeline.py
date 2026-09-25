"""
pipeline/run_pipeline.py
────────────────────────
Orchestrator — called by anacron daily and by `make run-pipeline`.
Runs stages M1 → M6 in sequence.  Each stage runs in a try/except so a
failure in one stage is logged but subsequent stages still attempt to run.

STUB — full implementation in Milestone 7.
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone

log = logging.getLogger(__name__)


def main() -> int:
    """Run the full pipeline.  Returns exit code (0 = success, 1 = partial failure)."""
    start = datetime.now(timezone.utc)
    log.info("=" * 60)
    log.info("Stock-News Pipeline started at %s", start.isoformat())
    log.info("=" * 60)

    errors: list[str] = []

    stages = [
        ("M1 Finviz scrape",        _run_scraper),
        ("M2 Body fetch",            _run_body_fetch),
        ("M3 LLM extraction",        _run_extraction),
        ("M4 Daily report",          _run_report),
        ("M5 Price data",            _run_prices),
        ("M6 Neon sync",             _run_neon_sync),
    ]

    for stage_name, fn in stages:
        try:
            log.info("→ Stage: %s", stage_name)
            fn()
            log.info("  ✓ %s complete.", stage_name)
        except NotImplementedError:
            log.info("  ⚠ %s not yet implemented (stub).", stage_name)
        except Exception as exc:
            log.error("  ✗ %s FAILED: %s", stage_name, exc, exc_info=True)
            errors.append(f"{stage_name}: {exc}")

    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    log.info("Pipeline finished in %.1f s — %d error(s).", elapsed, len(errors))

    return 1 if errors else 0


# ---------------------------------------------------------------------------
# Per-stage stubs — replaced by real implementations in later milestones
# ---------------------------------------------------------------------------

def _run_scraper() -> None:
    from pipeline.scraper.finviz import scrape
    scrape()


def _run_body_fetch() -> None:
    from pipeline.fetch.body_fetcher import fetch_bodies
    fetch_bodies()


def _run_extraction() -> None:
    from pipeline.extract.omniroute import run_extraction
    run_extraction()


def _run_report() -> None:
    from datetime import date
    from pipeline.db.local import LocalSession
    from pipeline.report.prompt_builder import build_report_prompt
    from pipeline.report.claude_web import generate_report
    
    with LocalSession() as session:
        trading_day = date.today()
        prompt = build_report_prompt(session, trading_day)
        
        if not prompt:
            log.info("  Not enough articles/sectors for a report today.")
            return
            
        # extract all unique article IDs from the prompt grouping logic
        # For simplicity, we just regex search or use a helper function, but wait!
        # `build_report_prompt` doesn't return the article_ids. Let's just query the db again.
        from pipeline.db.models import Article
        from sqlalchemy import select
        articles = session.execute(
            select(Article.id).where(Article.trading_day == trading_day, Article.status == "verified")
        ).scalars().all()
        
        generate_report(trading_day, prompt, list(articles))


def _run_prices() -> None:
    from pipeline.prices.finnhub import update_prices
    update_prices()


def _run_neon_sync() -> None:
    from pipeline.sync.neon_sync import sync_to_neon
    sync_to_neon()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    )
    sys.exit(main())
