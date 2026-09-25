import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from pipeline.config import settings
from pipeline.db.models import Base
from backend.main import app
from backend.db import get_db

# Override local_db_url to use test db
TEST_DB_URL = settings.local_db_url.replace("/stocknews", "/stocknews_test")

@pytest.fixture(scope="session")
def engine():
    # First, connect to default postgres db to create the test db
    default_url = settings.local_db_url.replace("/stocknews", "/postgres")
    setup_engine = create_engine(default_url, isolation_level="AUTOCOMMIT")
    with setup_engine.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS stocknews_test"))
        conn.execute(text("CREATE DATABASE stocknews_test"))
    setup_engine.dispose()

    # Now create the test engine
    test_engine = create_engine(TEST_DB_URL)
    Base.metadata.create_all(bind=test_engine)
    
    yield test_engine
    
    # Teardown
    test_engine.dispose()
    with setup_engine.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS stocknews_test"))

@pytest.fixture(scope="function")
def db_session(engine):
    """Provides a clean database session for each test."""
    connection = engine.connect()
    transaction = connection.begin()
    
    Session = sessionmaker(bind=connection)
    session = Session()
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        yield db_session
        
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
