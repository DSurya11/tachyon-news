from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.db import get_db
from pipeline.db.models import Report

router = APIRouter(prefix="/reports", tags=["reports"])


def _report_dict(report: Report) -> dict:
    return {
        "id": report.id,
        "trading_day": report.trading_day,
        "content": report.content,
        "article_ids": report.article_ids or [],
        "top_picks": report.top_picks or [],
        "created_at": report.created_at,
    }


@router.get("")
def list_reports(limit: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    """Report index (no content), newest first."""
    rows = db.execute(
        select(Report.trading_day, Report.created_at).order_by(desc(Report.trading_day)).limit(limit)
    ).all()
    # Which model or service wrote a brief stays internal: the dashboard never shows it.
    return {"reports": [{"trading_day": d, "created_at": c} for d, c in rows]}


@router.get("/latest")
def get_latest_report(db: Session = Depends(get_db)):
    """The most recent daily synthesis report."""
    report = db.execute(select(Report).order_by(desc(Report.trading_day)).limit(1)).scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="No reports available")
    return _report_dict(report)


@router.get("/{trading_day}")
def get_report(trading_day: date, db: Session = Depends(get_db)):
    report = db.execute(select(Report).where(Report.trading_day == trading_day)).scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail=f"No report for {trading_day}")
    return _report_dict(report)
