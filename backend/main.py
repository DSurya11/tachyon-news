"""
backend/main.py
───────────────
FastAPI application entry point.
Full implementation in Milestone 8. Stub for Milestone 0.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pipeline.config import settings

app = FastAPI(
    title="Stock-News Pipeline API",
    description="Public API for the stock-news pipeline dashboard.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


from backend.routers import news, reports, quotes
from backend.db import get_db
from sqlalchemy.orm import Session
from fastapi import Depends

@app.get("/health")
async def health(db: Session = Depends(get_db)):
    from pipeline.db.models import ScrapeRun, Article
    from sqlalchemy import select, desc
    
    last_run = db.execute(select(ScrapeRun).order_by(desc(ScrapeRun.started_at)).limit(1)).scalar_one_or_none()
    items = db.query(Article).count()
    
    return {
        "status": "ok",
        "last_scrape_at": last_run.started_at.isoformat() if last_run else None,
        "items_found": last_run.items_found if last_run else items,
        "errors": last_run.error_count if last_run else 0,
        "readiness": 100
    }

app.include_router(news.router)
app.include_router(reports.router)
app.include_router(quotes.router)
