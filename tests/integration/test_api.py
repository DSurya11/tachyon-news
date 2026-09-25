import pytest
from pipeline.db.models import Article, Report
from datetime import date, datetime

def test_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_news_endpoint(client, db_session):
    a1 = Article(canonical_url="http://test.com/news1", headline="News 1", status="verified", trading_day=date.today(), last_seen_at=datetime.utcnow())
    db_session.add(a1)
    db_session.commit()
    
    r = client.get("/news")
    assert r.status_code == 200
    data = r.json()
    assert "data" in data
    assert len(data["data"]) >= 1

def test_reports_latest(client, db_session):
    report = Report(trading_day=date.today(), content="Market is doing well", article_ids=[1,2,3])
    db_session.add(report)
    db_session.commit()
    
    r = client.get("/reports/latest")
    assert r.status_code == 200
    assert "Market is doing well" in r.json()["content"]

def test_quotes_endpoint(client):
    r = client.get("/quote/AAPL")
    assert r.status_code == 200
    assert "symbol" in r.json()
    
    r2 = client.get("/quotes?symbols=AAPL,NVDA")
    assert r2.status_code == 200
    assert len(r2.json()["data"]) == 2
