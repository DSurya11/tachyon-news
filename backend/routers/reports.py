from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from backend.db import get_db
from pipeline.db.models import Report

router = APIRouter(prefix="/reports", tags=["reports"])

@router.get("/latest")
def get_latest_report(db: Session = Depends(get_db)):
    """Get the most recent daily synthesis report."""
    report = db.execute(
        select(Report).order_by(desc(Report.trading_day)).limit(1)
    ).scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=404, detail="No reports available")
        
    return {
        "id": report.id,
        "trading_day": report.trading_day,
        "content": report.content,
        "article_ids": report.article_ids,
        "created_at": report.created_at
    }
