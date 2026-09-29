"""
Test configuration.

Tests NEVER touch the real databases or external services:
  - LOCAL_DB_URL / API_DB_URL are pointed at a throwaway `stocknews_test` DB
    (and `stocknews_test_neon` stands in for Neon in sync tests)
  - API keys are blanked so no test can reach Finnhub/Anthropic
Settings are patched *before* any module that creates an engine is imported.
"""
from __future__ import annotations

import tempfile
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from pipeline.config import settings

_BASE_URL = make_url(settings.local_db_url)
TEST_DB_URL = _BASE_URL.set(database="stocknews_test").render_as_string(hide_password=False)
TEST_NEON_URL = _BASE_URL.set(database="stocknews_test_neon").render_as_string(hide_password=False)
_ADMIN_URL = _BASE_URL.set(database="postgres").render_as_string(hide_password=False)

settings.local_db_url = TEST_DB_URL
settings.api_db_url = TEST_DB_URL
settings.neon_db_url = ""
settings.finnhub_api_key = ""
settings.anthropic_api_key = ""
settings.india_feeds = ""  # tests never reach real RSS feeds
settings.google_client_id = ""
settings.cors_origins = "*"  # the e2e dashboard runs on a random local port; .env may restrict origins
settings.cors_origin_regex = ""
settings.log_dir = tempfile.mkdtemp(prefix="stocknews-test-logs-")
settings.backup_dir = tempfile.mkdtemp(prefix="stocknews-test-backups-")
settings.alert_desktop = False  # tests never pop up notifications or call webhooks
settings.alert_webhook_url = ""
settings.healthcheck_url = ""


def _db_available() -> bool:
    try:
        eng = create_engine(_ADMIN_URL, isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 3})
        with eng.connect():
            pass
        eng.dispose()
        return True
    except Exception:
        return False


DB_AVAILABLE = _db_available()


def pytest_collection_modifyitems(config, items):
    if DB_AVAILABLE:
        return
    skip = pytest.mark.skip(reason="Postgres not reachable (run `make db-up`)")
    for item in items:
        if "integration" in str(item.fspath) or "e2e" in str(item.fspath):
            item.add_marker(skip)


def _recreate(name: str) -> None:
    admin = create_engine(_ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
        conn.execute(text(f"CREATE DATABASE {name}"))
    admin.dispose()


def _drop(name: str) -> None:
    admin = create_engine(_ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
    admin.dispose()


@pytest.fixture(scope="session")
def engine():
    """The pipeline's own engine, pointed at a fresh test database."""
    _recreate("stocknews_test")
    from pipeline.db.local import create_all_tables
    from pipeline.db.local import engine as local_engine

    create_all_tables()
    yield local_engine
    local_engine.dispose()
    from backend.db import engine as api_engine

    api_engine.dispose()
    _drop("stocknews_test")


@pytest.fixture
def clean_db(engine) -> Iterator[None]:
    """Empty every table before the test (for tests that commit through the pipeline)."""
    from pipeline.db.models import Base

    with engine.begin() as conn:
        names = ", ".join(t.name for t in Base.metadata.sorted_tables)
        conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def db_session(engine, clean_db):
    from pipeline.db.local import LocalSession

    with LocalSession() as session:
        yield session


@pytest.fixture
def anon_client(engine, clean_db, monkeypatch):
    """API client with no session (for auth tests). Yahoo history is offline unless a test stubs it."""
    from fastapi.testclient import TestClient

    from backend import auth, history

    history.reset_cache()
    monkeypatch.setattr(history, "_download", lambda *a: [])
    from backend.main import app
    from backend.routers import quotes

    quotes._quote_cache.clear()
    quotes._miss_cache.clear()
    from backend.routers import news

    news._summary_cache.clear()
    news._reaction_cache.clear()
    from backend import reaction

    reaction._group_cache.clear()
    auth._session_cache.clear()
    auth._attempts.clear()
    from backend import fx

    fx.reset_cache()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client(anon_client):
    """API client signed in as a fresh test user (every data endpoint needs a session)."""
    r = anon_client.post("/auth/signup", json={"email": "tester@example.com", "password": "correct horse"})
    assert r.status_code == 201, r.text
    anon_client.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return anon_client


@pytest.fixture
def neon_test_db(engine, monkeypatch):
    """A second database standing in for Neon."""
    _recreate("stocknews_test_neon")
    from sqlalchemy.orm import sessionmaker

    from pipeline.db import neon

    neon_engine = create_engine(TEST_NEON_URL)
    monkeypatch.setattr(neon, "neon_engine", neon_engine)
    monkeypatch.setattr(neon, "NeonSession", sessionmaker(bind=neon_engine))
    yield neon_engine
    neon_engine.dispose()
    _drop("stocknews_test_neon")
