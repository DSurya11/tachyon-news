from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from backend.db import get_db
from pipeline.config import settings
from pipeline.db.models import Article, Report, ScrapeRun

log = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


def readiness_pct(days_with_data: int) -> float:
    """Progress toward the readiness gate: days of extracted coverage vs GATE_MIN_DAYS."""
    if settings.gate_min_days <= 0:
        return 100.0
    return round(min(100.0, 100.0 * days_with_data / settings.gate_min_days), 1)


@router.get("/health")
def health(db: Session = Depends(get_db)):
    """Liveness + pipeline freshness. Returns 503 when the database is unreachable."""
    try:
        last_run = db.execute(select(ScrapeRun).order_by(desc(ScrapeRun.started_at)).limit(1)).scalar_one_or_none()
        since = datetime.now(UTC) - timedelta(hours=24)
        articles_24h = db.execute(select(func.count()).select_from(Article).where(Article.first_seen_at >= since)).scalar_one()
        days_with_data = db.execute(
            select(func.count(func.distinct(Article.trading_day))).where(Article.status.in_(("verified", "extracted")))
        ).scalar_one()
        latest_report = db.execute(select(func.max(Report.trading_day))).scalar_one()
    except Exception as exc:  # noqa: BLE001
        log.error("Health check DB error: %s", exc)
        return JSONResponse(status_code=503, content={"status": "error", "database": "unreachable"})

    stale = last_run is None or last_run.started_at < datetime.now(UTC) - timedelta(hours=3)
    return {
        "status": "degraded" if stale else "ok",
        "database": "ok",
        "last_scrape_at": last_run.started_at.isoformat() if last_run else None,
        "last_scrape_status": last_run.status if last_run else None,
        "items_found": last_run.items_found if last_run else 0,
        "errors": last_run.error_count if last_run else 0,
        "articles_24h": articles_24h,
        "latest_report_day": latest_report.isoformat() if latest_report else None,
        "days_with_data": days_with_data,
        "readiness": readiness_pct(days_with_data),
    }
