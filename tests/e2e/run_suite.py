#!/usr/bin/env python3
import sys
import logging
from unittest.mock import patch
from datetime import date
from sqlalchemy import text

# Add parent dir to path if run standalone
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from pipeline.db.local import LocalSession, engine
from pipeline.db.models import Base, Article, Extraction, PriceDaily
from pipeline.run_pipeline import main as run_pipeline
from backend.main import app
from fastapi.testclient import TestClient

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("e2e")

def setup_test_db():
    log.info("Provisioning fresh test database tables...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

def mock_scrape():
    from datetime import datetime
    log.info("Mocking Scraper...")
    with LocalSession() as session:
        a = Article(canonical_url="http://mock.com/1", headline="Mock Headline", status="new", trading_day=date.today(), body="Mock Body", last_seen_at=datetime.utcnow())
        session.add(a)
        session.commit()

def mock_body_fetch():
    log.info("Mocking Body Fetch...")
    with LocalSession() as session:
        articles = session.query(Article).filter_by(status="new").all()
        for a in articles:
            a.status = "body_fetched"
        session.commit()

def mock_omniroute():
    log.info("Mocking OmniRoute LLM Extraction...")
    with LocalSession() as session:
        articles = session.query(Article).filter_by(status="body_fetched").all()
        for a in articles:
            a.status = "verified"
            ext = Extraction(article_id=a.id, event_type="macro", sentiment="bullish", tickers=["MOCK"])
            session.add(ext)
        session.commit()

def mock_claude_web(trading_day, prompt, article_ids):
    from pipeline.db.models import Report
    log.info("Mocking Claude Report...")
    with LocalSession() as session:
        r = Report(trading_day=trading_day, content="Mocked Report", article_ids=article_ids)
        session.add(r)
        session.commit()

def run_suite():
    setup_test_db()
    
    log.info("=== Starting E2E Mock Pipeline ===")
    
    # We patch the actual stages in run_pipeline
    with patch("pipeline.run_pipeline._run_scraper", mock_scrape), \
         patch("pipeline.run_pipeline._run_body_fetch", mock_body_fetch), \
         patch("pipeline.run_pipeline._run_extraction", mock_omniroute), \
         patch("pipeline.report.claude_web.generate_report", mock_claude_web), \
         patch("pipeline.run_pipeline._run_neon_sync", lambda: None):
             
        # Mock finnhub using its built-in dummy logic (no need to patch)
        exit_code = run_pipeline()
        
    if exit_code != 0:
        log.error("Pipeline failed!")
        sys.exit(1)
        
    log.info("Pipeline complete. Asserting DB state...")
    with LocalSession() as session:
        assert session.query(Article).count() == 1
        assert session.query(Extraction).count() == 1
        assert session.query(PriceDaily).count() > 0 # from finnhub dummy
        
    log.info("Hitting FastAPI Test Server...")
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    
    r = client.get("/news")
    assert r.status_code == 200
    assert len(r.json()["data"]) == 1
    
    log.info("E2E Suite PASSED ✓")
    
if __name__ == "__main__":
    run_suite()
