from pipeline.db.local import engine
from sqlalchemy import text
with engine.connect() as conn:
    rows = conn.execute(text("SELECT pid, state, wait_event_type, wait_event, query FROM pg_stat_activity WHERE state != 'idle';")).fetchall()
    for r in rows:
        print(r)
