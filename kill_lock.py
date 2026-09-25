from pipeline.db.local import engine
from sqlalchemy import text
with engine.connect() as conn:
    conn.execute(text("SELECT pg_terminate_backend(15954);"))
    conn.commit()
