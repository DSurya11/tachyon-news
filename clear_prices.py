from pipeline.db.local import engine
from sqlalchemy import text
with engine.connect() as conn:
    conn.execute(text("TRUNCATE TABLE prices_daily;"))
    conn.commit()
