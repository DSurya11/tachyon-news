import logging
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import OperationalError

from pipeline.db.local import LocalSession
from pipeline.db.neon import NeonSession
from pipeline.db.models import (
    Article,
    ArticleTicker,
    Extraction,
    Ticker,
    PriceDaily,
    ScrapeRun,
    Report,
)

logger = logging.getLogger(__name__)

def sync_table(local_session, neon_session, model, pk_col, exclude_cols=None):
    """Upserts all rows from local table to Neon table."""
    exclude_cols = exclude_cols or []
    
    rows = local_session.execute(select(model)).scalars().all()
    if not rows:
        return 0

    dicts = []
    for row in rows:
        row_dict = {c.name: getattr(row, c.name) for c in model.__table__.columns if c.name not in exclude_cols}
        dicts.append(row_dict)

    stmt = insert(model).values(dicts)
    
    # Build update dict for ON CONFLICT DO UPDATE
    set_dict = {c.name: getattr(stmt.excluded, c.name) 
                for c in model.__table__.columns 
                if c.name not in exclude_cols and c.name != pk_col}

    if set_dict:
        stmt = stmt.on_conflict_do_update(
            index_elements=[pk_col] if isinstance(pk_col, str) else pk_col,
            set_=set_dict
        )
    else:
        stmt = stmt.on_conflict_do_nothing(
            index_elements=[pk_col] if isinstance(pk_col, str) else pk_col
        )
        
    neon_session.execute(stmt)
    return len(dicts)

def sync_to_neon():
    """Sync all local data to Neon DB."""
    if not NeonSession:
        logger.warning("NeonSession is not available. Skipping sync.")
        return

    try:
        with LocalSession() as local_session, NeonSession() as neon_session:
            # 1. Tickers
            c = sync_table(local_session, neon_session, Ticker, "symbol")
            logger.info(f"Synced {c} rows to Ticker")
            
            # 2. Articles (Exclude body, title_hash to save space)
            c = sync_table(local_session, neon_session, Article, "id", exclude_cols=["body", "title_hash"])
            logger.info(f"Synced {c} rows to Article")
            
            # 3. ArticleTickers (Composite PK)
            c = sync_table(local_session, neon_session, ArticleTicker, ["article_id", "ticker"])
            logger.info(f"Synced {c} rows to ArticleTicker")
            
            # 4. Extractions (Exclude evidence, key_facts to save space as per plan)
            c = sync_table(local_session, neon_session, Extraction, "id", exclude_cols=["evidence", "key_facts"])
            logger.info(f"Synced {c} rows to Extraction")
            
            # 5. Prices
            c = sync_table(local_session, neon_session, PriceDaily, ["ticker", "date"])
            logger.info(f"Synced {c} rows to PriceDaily")
            
            # 6. ScrapeRuns
            c = sync_table(local_session, neon_session, ScrapeRun, "id")
            logger.info(f"Synced {c} rows to ScrapeRun")
            
            # 7. Reports
            c = sync_table(local_session, neon_session, Report, "id")
            logger.info(f"Synced {c} rows to Report")
            
            neon_session.commit()
            logger.info("Neon sync complete.")
            
    except OperationalError as e:
        logger.warning(f"Could not connect to Neon DB (is NEON_DB_URL correct?): {e}")
    except Exception as e:
        logger.error(f"Error during Neon sync: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")
    sync_to_neon()
