"""
Full pipeline run through the real orchestrator with every external service
faked: Finviz HTML, article pages, the LLM router, the report writer,
yfinance and Neon (a second local database).
"""
from datetime import date

import httpx
import pandas as pd
import pytest
from sqlalchemy import text

from pipeline import run_pipeline
from pipeline.config import settings
from pipeline.db.local import LocalSession
from pipeline.db.models import Article, Report, ScrapeRun
from pipeline.extract import omniroute
from pipeline.fetch import body_fetcher
from pipeline.prices import yahoo
from pipeline.report import providers, service
from pipeline.scraper import finviz
from tests.fakes import FakeLLM
from tests.fixtures import ARTICLE_PAGE_HTML, FINVIZ_HTML, GOOD_EXTRACTION_JSON, REPORT_MARKDOWN


def _article_server(request: httpx.Request) -> httpx.Response:
    if request.url.host.endswith("example.com"):
        return httpx.Response(200, html=ARTICLE_PAGE_HTML)
    return httpx.Response(403)


def _fake_download(symbols, start, end, **kw):
    days = pd.date_range(end=date.today(), periods=3, freq="D")
    cols = pd.MultiIndex.from_product([symbols, ["Open", "High", "Low", "Close", "Volume"]])
    df = pd.DataFrame(1.0, index=days, columns=cols)
    df.iloc[0, 0] = float("nan")  # a gap yfinance sometimes returns
    return df


@pytest.fixture
def faked_world(monkeypatch, neon_test_db, clean_db):
    async def fake_page(url):
        return FINVIZ_HTML

    monkeypatch.setattr(finviz, "_fetch_page_html", fake_page)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        body_fetcher.httpx, "AsyncClient",
        lambda **kw: real_client(transport=httpx.MockTransport(_article_server), **kw),
    )
    monkeypatch.setattr(body_fetcher, "RETRIES", 1)

    monkeypatch.setattr(omniroute, "make_client", lambda: FakeLLM(lambda kw: GOOD_EXTRACTION_JSON))

    fake_providers = {"omniroute": lambda prompt: REPORT_MARKDOWN}
    monkeypatch.setattr(providers, "PROVIDERS", fake_providers)
    monkeypatch.setattr(service, "PROVIDERS", fake_providers)
    monkeypatch.setattr(settings, "report_providers", "omniroute")
    monkeypatch.setattr(settings, "report_min_articles", 1)

    monkeypatch.setattr(yahoo.yf, "download", _fake_download)
    monkeypatch.setattr(settings, "fetch_skip_domains", "")


def test_full_pipeline_run(faked_world, neon_test_db):
    assert run_pipeline.main([]) == 0

    with LocalSession() as s:
        by_headline = {a.headline[:6]: a for a in s.query(Article)}
        nvda, acme, fed = by_headline["Nvidia"], by_headline["Acme D"], by_headline["Fed ho"]

        assert nvda.status == "verified" and nvda.content_quality == "full"
        assert nvda.url.startswith("https://www.Example.com/Markets")
        assert acme.status == "noise_tagged" and acme.body is None  # never fetched
        assert fed.status == "extracted" and fed.body is None  # 403 → headline-only; cannot be verified
        run = s.query(ScrapeRun).one()
        assert run.status == "done" and run.items_found == 3
        assert run.per_domain_stats["example.com"]["fetched"] == 1
        assert run.per_domain_stats["macro.example.org"]["failed"] == 1

        report = s.query(Report).one()
        assert report.provider == "omniroute" and nvda.id in report.article_ids

    with neon_test_db.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM articles WHERE body IS NOT NULL")).scalar_one() == 0
        assert conn.execute(text("SELECT count(*) FROM reports")).scalar_one() == 1
        assert conn.execute(text("SELECT count(*) FROM prices_daily WHERE close = 'NaN'")).scalar_one() == 0

    # A second run is a no-op for extraction and keeps the report.
    assert run_pipeline.main(["--skip", "sync"]) == 0


def test_failed_stage_is_reported_but_later_stages_run(faked_world, monkeypatch):
    async def broken(url):
        raise RuntimeError("finviz down")

    monkeypatch.setattr(finviz, "_fetch_page_html", broken)
    assert run_pipeline.main(["--only", "scrape", "prices"]) == 1
    with LocalSession() as s:
        assert s.query(ScrapeRun).one().status == "failed"


def test_overlapping_runs_are_skipped(faked_world, monkeypatch):
    with run_pipeline.run_lock():
        called = []
        monkeypatch.setattr(run_pipeline, "run", lambda *a, **k: called.append(1) or 0)
        assert run_pipeline.main([]) == 0
        assert called == []


def test_only_runs_selected_stages_in_canonical_order(monkeypatch, clean_db):
    ran = []
    stages = {k: (name, lambda ctx, k=k: ran.append(k)) for k, (name, _) in run_pipeline.STAGES.items()}
    monkeypatch.setattr(run_pipeline, "STAGES", stages)
    assert run_pipeline.main(["--only", "sync", "scrape"]) == 0
    assert ran == ["scrape", "sync"]
