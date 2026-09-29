"""
pipeline/report/service.py
──────────────────────────
Decides whether the daily report needs (re)writing and runs the provider chain.

A report is written for the *current* trading day (ET, weekends → Monday) when
  - there is no report yet and at least REPORT_MIN_ARTICLES usable articles, or
  - REPORT_REFRESH_NEW_ARTICLES more articles arrived since the last version.
This keeps the hourly pipeline from rewriting the report every hour.

CLI:
    python -m pipeline.report.service                 # same rules as the pipeline
    python -m pipeline.report.service --force         # rewrite now
    python -m pipeline.report.service --day 2026-09-28 --provider omniroute
"""
from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy.dialects.postgresql import insert as pg_insert

from pipeline.config import settings
from pipeline.db.local import LocalSession
from pipeline.db.models import Report
from pipeline.market_time import current_trading_day
from pipeline.report.prompt_builder import build_report_prompt, count_reportable_articles
from pipeline.report.providers import PROVIDERS, ProviderUnavailable
from pipeline.report.top_picks import split_top_picks

log = logging.getLogger(__name__)


@dataclass
class ReportOutcome:
    trading_day: date
    status: str  # written | skipped
    reason: str
    provider: str | None = None


class ReportGenerationError(RuntimeError):
    pass


def _should_write(existing: Report | None, usable: int, new_articles: int, force: bool) -> tuple[bool, str]:
    if force:
        return True, "forced"
    if usable < settings.report_min_articles:
        return False, f"only {usable} usable articles (< {settings.report_min_articles})"
    if existing is None:
        return True, "no report yet"
    if new_articles >= settings.report_refresh_new_articles:
        return True, f"{new_articles} new articles since last version"
    return False, f"report is current ({new_articles} new articles)"


def _save(trading_day: date, content: str, article_ids: list[int], provider: str, top_picks: list[dict]) -> None:
    now = datetime.now(UTC)
    values = {"content": content, "article_ids": article_ids, "provider": provider, "top_picks": top_picks, "created_at": now}
    with LocalSession() as session:
        stmt = pg_insert(Report).values(trading_day=trading_day, **values)
        stmt = stmt.on_conflict_do_update(index_elements=["trading_day"], set_=values)
        session.execute(stmt)
        session.commit()


def generate_daily_report(
    trading_day: date | None = None,
    force: bool = False,
    providers: list[str] | None = None,
) -> ReportOutcome:
    trading_day = trading_day or current_trading_day()

    with LocalSession() as session:
        existing = session.query(Report).filter_by(trading_day=trading_day).one_or_none()
        usable = count_reportable_articles(session, trading_day)
        new_articles = (
            count_reportable_articles(session, trading_day, extracted_after=existing.created_at) if existing else usable
        )
        write, reason = _should_write(existing, usable, new_articles, force)
        if not write:
            log.info("Report for %s skipped: %s", trading_day, reason)
            return ReportOutcome(trading_day, "skipped", reason)
        prompt = build_report_prompt(session, trading_day)

    if prompt is None:
        return ReportOutcome(trading_day, "skipped", "no extracted articles")

    log.info(
        "Writing report for %s (%s): %d articles, %d sectors, prompt %d chars",
        trading_day, reason, len(prompt.article_ids), len(prompt.sectors), len(prompt.user),
    )

    failures: list[str] = []
    for name in providers or settings.report_provider_list:
        provider = PROVIDERS.get(name)
        if provider is None:
            failures.append(f"{name}: unknown provider")
            continue
        try:
            content = provider(prompt)
        except ProviderUnavailable as exc:
            log.info("Report provider %s unavailable: %s", name, exc)
            failures.append(f"{name}: {exc}")
            continue
        except Exception as exc:
            log.warning("Report provider %s failed: %s", name, exc, exc_info=True)
            failures.append(f"{name}: {exc}")
            continue
        content, picks = split_top_picks(content, prompt.article_ids, settings.report_top_picks)
        _save(trading_day, content, prompt.article_ids, name, picks)
        log.info("Report for %s written by %s (%d chars, %d top picks)", trading_day, name, len(content), len(picks))
        return ReportOutcome(trading_day, "written", reason, provider=name)

    raise ReportGenerationError("all report providers failed — " + " | ".join(failures))


def main(argv: list[str] | None = None) -> int:
    from pipeline.logging_setup import setup_logging

    setup_logging("report.log")
    parser = argparse.ArgumentParser(description="Generate the daily market report")
    parser.add_argument("--day", type=date.fromisoformat, help="Trading day (YYYY-MM-DD); default: current")
    parser.add_argument("--force", action="store_true", help="Rewrite even if the report is current")
    parser.add_argument("--provider", action="append", choices=sorted(PROVIDERS), help="Provider(s) to try, in order")
    args = parser.parse_args(argv)
    try:
        outcome = generate_daily_report(args.day, force=args.force, providers=args.provider)
    except ReportGenerationError as exc:
        log.error("%s", exc)
        return 1
    print(f"{outcome.trading_day}: {outcome.status} ({outcome.reason})" + (f" via {outcome.provider}" if outcome.provider else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
