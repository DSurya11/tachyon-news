from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert
import pytest
from datetime import date, datetime
from pipeline.db.models import Article, Ticker, PriceDaily

def test_article_unique_canonical_url(db_session):
    a1 = Article(canonical_url="http://test.com/1", headline="Test 1", last_seen_at=datetime.utcnow())
    db_session.add(a1)
    db_session.commit()
    
    a2 = Article(canonical_url="http://test.com/1", headline="Test 2", last_seen_at=datetime.utcnow())
    db_session.add(a2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

def test_price_daily_upsert(db_session):
    stmt = insert(PriceDaily).values({
        "ticker": "AAPL",
        "date": date(2023, 1, 1),
        "open": 100.0,
        "close": 110.0
    })
    db_session.execute(stmt)
    db_session.commit()
    
    # Upsert with new close
    stmt2 = insert(PriceDaily).values({
        "ticker": "AAPL",
        "date": date(2023, 1, 1),
        "open": 100.0,
        "close": 120.0
    })
    stmt2 = stmt2.on_conflict_do_update(
        index_elements=["ticker", "date"],
        set_={"close": stmt2.excluded.close}
    )
    db_session.execute(stmt2)
    db_session.commit()
    
    p = db_session.query(PriceDaily).filter_by(ticker="AAPL").first()
    assert p.close == 120.0
