"""
pipeline/run_pipeline.py
────────────────────────
Orchestrator — run hourly by cron (`make setup-scheduler`) or by hand
(`make run-pipeline`).

Stages run in order; a failing stage is logged and recorded but later stages
still run.  A file lock guarantees that two runs never overlap (a slow run
used to collide with the next hourly one).

    python -m pipeline.run_pipeline                       # all stages
    python -m pipeline.run_pipeline --only scrape fetch   # a subset (stages: scrape india fetch extract report prices outcomes sync)
    python -m pipeline.run_pipeline --skip report sync
    python -m pipeline.run_pipeline --force-report
    python -m pipeline.run_pipeline --unattended          # the scheduled job: alerts on repeated failures
"""
from __future__ import annotations

import argparse
import fcntl
import logging
import signal
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from pipeline.config import settings

log = logging.getLogger("pipeline.run")

LOCK_FILE = Path(settings.log_dir) / ".pipeline.lock"


@dataclass
class RunContext:
    force_report: bool = False
    scrape_run_id: int | None = None
    results: dict[str, object] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------

def _stage_schema(ctx: RunContext) -> object:
    from pipeline.db.local import create_all_tables

    create_all_tables()
    return "ok"


def _stage_scrape(ctx: RunContext) -> object:
    from pipeline.scraper.finviz import scrape

    run = scrape()
    ctx.scrape_run_id = run.id
    return {"found": run.items_found, "new": run.items_new, "updated": run.items_updated}


def _stage_india(ctx: RunContext) -> object:
    from pipeline.scraper.india_rss import scrape_india

    return scrape_india()


def _stage_fetch(ctx: RunContext) -> object:
    from pipeline.fetch.body_fetcher import fetch_bodies

    stats = fetch_bodies(scrape_run_id=ctx.scrape_run_id)
    return {k: sum(d.get(k, 0) for d in stats.values()) for k in ("fetched", "failed", "skipped", "full")}


def _stage_extract(ctx: RunContext) -> object:
    from pipeline.extract.omniroute import run_extraction

    return run_extraction()


def _stage_report(ctx: RunContext) -> object:
    from pipeline.report.service import generate_daily_report

    outcome = generate_daily_report(force=ctx.force_report)
    return f"{outcome.status} for {outcome.trading_day}: {outcome.reason}" + (
        f" via {outcome.provider}" if outcome.provider else ""
    )


def _stage_prices(ctx: RunContext) -> object:
    from pipeline.prices.yahoo import update_prices

    return update_prices()


def _stage_outcomes(ctx: RunContext) -> object:
    from pipeline.prices.outcomes import compute_outcomes

    return compute_outcomes()


def _stage_sync(ctx: RunContext) -> object:
    from pipeline.sync.neon_sync import sync_to_neon

    counts = sync_to_neon()
    return "skipped (NEON_DB_URL not set)" if counts is None else f"{sum(counts.values())} rows"


STAGES: dict[str, tuple[str, Callable[[RunContext], object]]] = {
    "scrape": ("M1 Finviz scrape", _stage_scrape),
    "india": ("M1b India feeds", _stage_india),
    "fetch": ("M2 Body fetch", _stage_fetch),
    "extract": ("M3 LLM extraction", _stage_extract),
    "report": ("M4 Daily report", _stage_report),
    "prices": ("M5 Price data", _stage_prices),
    "outcomes": ("M5b Story outcomes", _stage_outcomes),
    "sync": ("M6 Neon sync", _stage_sync),
}


# ---------------------------------------------------------------------------
# Lock
# ---------------------------------------------------------------------------

class AlreadyRunning(RuntimeError):
    pass


class Stopped(BaseException):
    """SIGTERM arrived (shutdown, logout, `systemctl stop`, scripts/stop.sh)."""


def _on_sigterm(signum, frame) -> None:
    raise Stopped()


@contextmanager
def run_lock(path: Path = LOCK_FILE) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise AlreadyRunning(f"another pipeline run holds {path}") from exc
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run(stage_keys: list[str], force_report: bool = False, ctx: RunContext | None = None) -> int:
    """Run the selected stages. Returns 0 on success, 1 if any stage failed."""
    ctx = ctx or RunContext(force_report=force_report)
    started = time.monotonic()
    log.info("=" * 60)
    log.info("Pipeline started — stages: %s", ", ".join(stage_keys))

    try:
        _stage_schema(ctx)
    except Exception as exc:
        log.critical("Database unavailable or schema upgrade failed: %s", exc, exc_info=True)
        ctx.results["schema"] = f"FAILED: {exc}"
        return 1

    errors: list[str] = []
    for key in stage_keys:
        name, fn = STAGES[key]
        t0 = time.monotonic()
        log.info("→ %s", name)
        try:
            result = fn(ctx)
        except Exception as exc:
            log.error("  ✗ %s FAILED after %.1fs: %s", name, time.monotonic() - t0, exc, exc_info=True)
            errors.append(f"{name}: {exc}")
            ctx.results[key] = f"FAILED: {exc}"
            continue
        ctx.results[key] = result
        log.info("  ✓ %s (%.1fs) %s", name, time.monotonic() - t0, result)

    log.info("Pipeline finished in %.1fs — %d failed stage(s).", time.monotonic() - started, len(errors))
    for err in errors:
        log.info("  failed: %s", err)
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    from pipeline.logging_setup import setup_logging

    parser = argparse.ArgumentParser(description="Run the stock-news pipeline")
    parser.add_argument("--only", nargs="+", choices=list(STAGES), help="Run only these stages")
    parser.add_argument("--skip", nargs="+", choices=list(STAGES), default=[], help="Skip these stages")
    parser.add_argument("--force-report", action="store_true", help="Rewrite today's report even if current")
    parser.add_argument(
        "--unattended", action="store_true",
        help="Scheduled run: alert on repeated stage failures (pipeline/ops/alerts.py) and exit 0 when only "
             "stages failed, so the scheduler reports real crashes only",
    )
    args = parser.parse_args(argv)

    setup_logging("pipeline.log")
    stages = [k for k in STAGES if (not args.only or k in args.only) and k not in args.skip]

    ctx = RunContext(force_report=args.force_report)
    # A shutdown mid-run ends it cleanly: browsers close, the lock is released, and the
    # work left undone (stories still new or unextracted) is simply picked up next run.
    previous = signal.signal(signal.SIGTERM, _on_sigterm)
    try:
        with run_lock():
            code = run(stages, force_report=args.force_report, ctx=ctx)
    except AlreadyRunning as exc:
        log.warning("Skipping this run: %s", exc)
        return 0
    except Stopped:
        log.warning("Run stopped before finishing (shutdown or stop request); the next run picks up where it left off.")
        return 0
    except BaseException as exc:
        if args.unattended:
            from pipeline.ops.alerts import after_run

            after_run(ctx.results, crashed=exc)
        raise
    finally:
        signal.signal(signal.SIGTERM, previous)
    if args.unattended:
        from pipeline.ops.alerts import after_run

        after_run(ctx.results)
        return 0
    return code


if __name__ == "__main__":
    sys.exit(main())
