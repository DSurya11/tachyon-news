import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pipeline.config import settings

# Priority:
# 1. RENDER_DB_URL (if set in production)
# 2. NEON_DB_URL (if provided and valid)
# 3. LOCAL_DB_URL (fallback for local development)
db_url = os.getenv("RENDER_DB_URL") or settings.neon_db_url

if not db_url or "CHANGEME" in db_url:
    db_url = settings.local_db_url

# For Neon, require sslmode=require
connect_args = {}
if "neon.tech" in db_url:
    connect_args["sslmode"] = "require"

engine = create_engine(
    db_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    connect_args=connect_args
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
