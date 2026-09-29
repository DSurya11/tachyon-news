from datetime import UTC, date, datetime

import pytest
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from pipeline.db.models import Article, PriceDaily
from pipeline.db.schema import EXPECTED_TABLES, ensure_schema, missing_tables


def test_schema_is_complete_and_upgrades_are_idempotent(engine):
    ensure_schema(engine)
    ensure_schema(engine)
    assert missing_tables(engine) == set()
    assert len(EXPECTED_TABLES) == 13


def test_article_unique_canonical_url(db_session):
    now = datetime.now(UTC)
    db_session.add(Article(canonical_url="http://test.com/1", headline="Test 1", last_seen_at=now))
    db_session.commit()
    db_session.add(Article(canonical_url="http://test.com/1", headline="Test 2", last_seen_at=now))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_new_article_defaults(db_session):
    art = Article(canonical_url="http://test.com/2", headline="T", last_seen_at=datetime.now(UTC))
    db_session.add(art)
    db_session.commit()
    db_session.refresh(art)
    assert (art.status, art.extraction_attempts, art.seen_count) == ("new", 0, 1)


def test_price_daily_upsert(db_session):
    for close in (110.0, 120.0):
        stmt = insert(PriceDaily).values(ticker="AAPL", date=date(2023, 1, 1), open=100.0, close=close)
        db_session.execute(stmt.on_conflict_do_update(index_elements=["ticker", "date"], set_={"close": stmt.excluded.close}))
        db_session.commit()
    assert db_session.query(PriceDaily).filter_by(ticker="AAPL").one().close == 120


def test_timestamp_defaults_are_evaluated_per_insert(engine):
    """Regression: server_default='now()' used to freeze to the CREATE TABLE time."""
    from sqlalchemy import text

    with engine.connect() as conn:
        defaults = dict(
            conn.execute(
                text(
                    "SELECT table_name || '.' || column_name, column_default FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND column_name IN ('created_at', 'first_seen_at')"
                )
            ).all()
        )
    assert defaults and all(d == "now()" for d in defaults.values()), defaults
