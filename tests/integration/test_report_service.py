from datetime import date

import pytest

from pipeline.config import settings
from pipeline.db.local import LocalSession
from pipeline.db.models import Report
from pipeline.report import providers, service
from pipeline.report.prompt_builder import build_report_prompt
from pipeline.report.providers import ProviderUnavailable
from tests.factories import add_article
from tests.fixtures import REPORT_MARKDOWN

DAY = date(2026, 9, 28)


@pytest.fixture
def articles(db_session, monkeypatch):
    monkeypatch.setattr(settings, "report_min_articles", 2)
    monkeypatch.setattr(settings, "report_refresh_new_articles", 2)
    return [add_article(db_session, id_hint=str(i), trading_day=DAY, tickers=(t,), sector=s)
            for i, (t, s) in enumerate([("NVDA", "Technology"), ("JPM", "Financials"), ("XOM", "Energy")])]


def _providers(monkeypatch, **fns):
    monkeypatch.setattr(providers, "PROVIDERS", fns)
    monkeypatch.setattr(service, "PROVIDERS", fns)


def test_prompt_groups_by_sector_and_lists_ids(db_session, articles):
    prompt = build_report_prompt(db_session, DAY)
    assert prompt.sectors == {"Energy": 1, "Financials": 1, "Technology": 1}
    assert prompt.article_ids == sorted(a.id for a in articles)
    assert "### SECTOR: Technology" in prompt.user and '"id": ' in prompt.user
    assert "Cite the source article id" in prompt.system


def test_first_working_provider_wins(monkeypatch, articles):
    def unavailable(p):
        raise ProviderUnavailable("no key")

    def broken(p):
        raise RuntimeError("boom")

    _providers(monkeypatch, anthropic=unavailable, claude_web=broken, omniroute=lambda p: REPORT_MARKDOWN)
    outcome = service.generate_daily_report(DAY, providers=["anthropic", "claude_web", "omniroute"])
    assert (outcome.status, outcome.provider) == ("written", "omniroute")
    with LocalSession() as s:
        report = s.query(Report).filter_by(trading_day=DAY).one()
        assert report.provider == "omniroute" and len(report.article_ids) == 3


def test_all_providers_failing_raises(monkeypatch, articles):
    def unavailable(p):
        raise ProviderUnavailable("nope")

    _providers(monkeypatch, omniroute=unavailable)
    with pytest.raises(service.ReportGenerationError, match="omniroute: nope"):
        service.generate_daily_report(DAY, providers=["omniroute"])


def test_report_is_not_rewritten_until_enough_new_articles(monkeypatch, db_session, articles):
    calls = []
    _providers(monkeypatch, omniroute=lambda p: calls.append(p) or REPORT_MARKDOWN)
    assert service.generate_daily_report(DAY, providers=["omniroute"]).status == "written"
    assert service.generate_daily_report(DAY, providers=["omniroute"]).status == "skipped"
    add_article(db_session, id_hint="n1", trading_day=DAY)
    add_article(db_session, id_hint="n2", trading_day=DAY)
    assert service.generate_daily_report(DAY, providers=["omniroute"]).status == "written"
    assert service.generate_daily_report(DAY, providers=["omniroute"], force=True).status == "written"
    assert len(calls) == 3


def test_too_few_articles_skips(monkeypatch, clean_db):
    _providers(monkeypatch, omniroute=lambda p: REPORT_MARKDOWN)
    outcome = service.generate_daily_report(DAY, providers=["omniroute"])
    assert outcome.status == "skipped" and "usable articles" in outcome.reason


def test_short_output_is_rejected(monkeypatch, articles):
    _providers(monkeypatch, omniroute=lambda p: providers._check("tiny", "omniroute"))
    with pytest.raises(service.ReportGenerationError, match="short"):
        service.generate_daily_report(DAY, providers=["omniroute"])


def test_claude_web_needs_a_display(monkeypatch, db_session, articles):
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setattr(settings, "claude_headless", False)
    with pytest.raises(ProviderUnavailable, match="display"):
        providers.generate_with_claude_web(build_report_prompt(db_session, DAY))


def test_anthropic_needs_a_key(db_session, articles):
    with pytest.raises(ProviderUnavailable):
        providers.generate_with_anthropic(build_report_prompt(db_session, DAY))


def test_india_stories_get_their_own_group_and_top_picks_are_stored(monkeypatch, db_session, articles):
    india = add_article(db_session, id_hint="in", trading_day=DAY, tickers=(), market="india", headline="Sensex falls")
    prompt = build_report_prompt(db_session, DAY)
    assert prompt.sectors["India Markets"] == 1
    assert '"top_picks"' in prompt.system and f"{settings.report_top_picks} stories" in prompt.system

    ids = [india.id, articles[0].id]
    block = '\n\n```json\n{"top_picks": [' + ", ".join(f'{{"id": {i}, "why": "matters"}}' for i in ids) + ', {"id": 424242}]}\n```'
    _providers(monkeypatch, omniroute=lambda p: REPORT_MARKDOWN + block)
    service.generate_daily_report(DAY, providers=["omniroute"], force=True)
    with LocalSession() as s:
        report = s.query(Report).filter_by(trading_day=DAY).one()
        assert report.content == REPORT_MARKDOWN.strip()  # the block never reaches readers
        assert report.top_picks == [{"id": ids[0], "rank": 1, "why": "matters"}, {"id": ids[1], "rank": 2, "why": "matters"}]
