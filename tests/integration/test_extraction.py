import pytest

from pipeline.config import settings
from pipeline.db.local import LocalSession
from pipeline.db.models import Article, Extraction
from pipeline.extract import omniroute
from tests.factories import add_article
from tests.fakes import FakeLLM, connection_error
from tests.fixtures import ARTICLE_BODY, GOOD_EXTRACTION_JSON


@pytest.fixture
def pending(db_session):
    def make(n=1, body=ARTICLE_BODY, **kw):
        return [add_article(db_session, id_hint=f"p{i}", status="body_fetched", extraction=False, body=body, **kw).id
                for i in range(n)]
    return make


def _use(monkeypatch, llm):
    monkeypatch.setattr(omniroute, "make_client", lambda: llm)
    monkeypatch.setattr(omniroute.time, "sleep", lambda s: None)
    return llm


def _article(aid):
    with LocalSession() as s:
        return s.get(Article, aid)


def test_successful_extraction_is_verified(monkeypatch, pending):
    (aid,) = pending()
    llm = _use(monkeypatch, FakeLLM([GOOD_EXTRACTION_JSON]))
    stats = omniroute.run_extraction()
    assert stats == {"extracted": 1, "verified": 1, "failed": 0, "skipped": 0, "aborted": False}
    art = _article(aid)
    assert (art.status, art.extraction_attempts) == ("verified", 1)
    assert llm.calls[0]["response_format"] == {"type": "json_object"}
    with LocalSession() as s:
        ext = s.query(Extraction).filter_by(article_id=aid).one()
        assert (ext.tickers, ext.model_used) == (["NVDA"], "fake-model")


def test_ungrounded_extraction_is_extracted_not_verified(monkeypatch, pending):
    (aid,) = pending(body="Completely different text about bananas.")
    _use(monkeypatch, FakeLLM([GOOD_EXTRACTION_JSON]))
    omniroute.run_extraction()
    assert _article(aid).status == "extracted"


def test_unparseable_reply_gets_one_corrective_retry(monkeypatch, pending):
    (aid,) = pending()
    llm = _use(monkeypatch, FakeLLM(["Let me think about the tickers...", GOOD_EXTRACTION_JSON]))
    omniroute.run_extraction()
    assert _article(aid).status == "verified"
    assert len(llm.calls) == 2 and "not a complete JSON object" in llm.calls[1]["messages"][-1]["content"]


def test_failures_are_retried_on_later_runs_up_to_the_limit(monkeypatch, pending):
    (aid,) = pending()
    _use(monkeypatch, FakeLLM(lambda kw: "garbage"))
    for attempt in range(1, settings.extraction_max_attempts + 2):
        omniroute.run_extraction()
        art = _article(aid)
        assert art.status == "extraction_failed"
        assert art.extraction_attempts == min(attempt, settings.extraction_max_attempts)


def test_outage_leaves_articles_untouched_and_fails_the_stage(monkeypatch, pending):
    ids = pending(n=settings.extraction_max_consecutive_errors + 2)
    _use(monkeypatch, FakeLLM(lambda kw: connection_error()))
    with pytest.raises(omniroute.LLMUnavailableError):
        omniroute.run_extraction()
    for aid in ids:
        art = _article(aid)
        assert (art.status, art.extraction_attempts) == ("body_fetched", 0)


def test_router_without_json_mode_is_handled(monkeypatch, pending):
    import httpx
    from openai import BadRequestError

    pending()
    def reply(kwargs):
        if "response_format" in kwargs:
            req = httpx.Request("POST", "http://x")
            return BadRequestError("response_format not supported", response=httpx.Response(400, request=req), body=None)
        return GOOD_EXTRACTION_JSON
    llm = _use(monkeypatch, FakeLLM(reply))
    assert omniroute.run_extraction()["verified"] == 1
    assert "response_format" not in llm.calls[-1]


def test_max_articles_cap(monkeypatch, pending):
    pending(n=3)
    _use(monkeypatch, FakeLLM(lambda kw: GOOD_EXTRACTION_JSON))
    assert omniroute.run_extraction(max_articles=2)["extracted"] == 2


def test_concurrent_workers_never_process_an_article_twice(monkeypatch, pending):
    ids = pending(n=9)
    llm = _use(monkeypatch, FakeLLM(lambda kw: GOOD_EXTRACTION_JSON))
    stats = omniroute.run_extraction(concurrency=3)
    assert stats["extracted"] == 9 and len(llm.calls) == 9
    with LocalSession() as s:
        assert s.query(Extraction).filter(Extraction.article_id.in_(ids)).count() == 9
