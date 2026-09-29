from sqlalchemy import text

from pipeline.db.models import Report
from pipeline.sync.neon_sync import sync_to_neon
from tests.factories import add_article, add_prices


def test_sync_copies_public_data_and_strips_private_columns(db_session, neon_test_db):
    art = add_article(db_session, body="secret full body")
    add_prices(db_session, "NVDA", [1.0, 2.0])
    db_session.add(Report(trading_day=art.trading_day, content="report", article_ids=[art.id], provider="omniroute"))
    db_session.commit()

    counts = sync_to_neon()
    assert counts["articles"] == 1 and counts["prices_daily"] == 2 and counts["reports"] == 1

    with neon_test_db.connect() as conn:
        body, title_hash, url = conn.execute(text("SELECT body, title_hash, url FROM articles")).one()
        assert body is None and title_hash is None and url == art.url
        evidence, key_facts, one_line = conn.execute(text("SELECT evidence, key_facts, one_line FROM extractions")).one()
        assert evidence is None and key_facts is None and one_line == "Summary 1"
        assert conn.execute(text("SELECT provider FROM reports")).scalar_one() == "omniroute"

    # idempotent upsert
    art_status = "extracted"
    db_session.query(type(art)).filter_by(id=art.id).update({"status": art_status})
    db_session.commit()
    sync_to_neon()
    with neon_test_db.connect() as conn:
        assert conn.execute(text("SELECT count(*), max(status) FROM articles")).one() == (1, art_status)


def test_sync_is_skipped_without_neon(clean_db):
    assert sync_to_neon() is None
