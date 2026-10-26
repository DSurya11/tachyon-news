"""Ask the news against a scripted model: free, and the same every run."""
from __future__ import annotations

import json
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from backend import ask, ask_tools
from backend.routers import ask as ask_router
from pipeline.config import settings
from pipeline.db.models import EventOutcome
from tests.factories import NOW, add_article, add_prices


def call(name: str, **arguments):
    return SimpleNamespace(id=f"c-{name}", function=SimpleNamespace(name=name, arguments=json.dumps(arguments)))


class Script:
    """`chat.completions.create` returning tool calls in order; records each request's messages."""

    def __init__(self, *turns):
        self.turns, self.requests = list(turns), []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **request):
        self.requests.append([dict(m) for m in request["messages"]])
        calls = self.turns.pop(0) if len(self.turns) > 1 else self.turns[0]
        message = SimpleNamespace(content=None, tool_calls=list(calls))
        return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="tool_calls")],
                               model="fake-model", usage=SimpleNamespace(prompt_tokens=100, completion_tokens=10))

    def tool_results(self, request: int) -> list[str]:
        return [m["content"] for m in self.requests[request] if m["role"] == "tool"]


@pytest.fixture(autouse=True)
def fresh_limits():
    ask_router.reset_limits()
    yield
    ask_router.reset_limits()


def test_a_cited_answer_passes_and_unverified_stories_are_said_by_code(db_session):
    good = add_article(db_session, id_hint="a", tickers=("JPM",), sector="Financials", sentiment="bearish")
    shaky = add_article(db_session, id_hint="b", tickers=("BAC",), sector="Financials", sentiment="bearish", status="extracted")
    model = Script([call("search_stories", sector="Financials", sentiment="bearish")],
                   [call("give_answer", answer="Two bearish bank stories.", story_ids=[good.id, shaky.id])])
    result = ask.ask("negative bank news", db_session, client=model)
    assert result.stopped == "answered" and result.story_ids == [good.id, shaky.id]
    assert result.total_matching == 2
    assert "1 of the 2 stories below is not verified" in result.answer


def test_an_id_no_tool_returned_is_refused_and_the_model_told(db_session):
    story = add_article(db_session)
    model = Script([call("search_stories", ticker="NVDA")],
                   [call("give_answer", answer="NVDA news.", story_ids=[story.id, 999999])],
                   [call("give_answer", answer="NVDA news.", story_ids=[story.id])])
    result = ask.ask("nvidia", db_session, client=model)
    assert "[999999]" in model.tool_results(2)[-1]
    assert result.story_ids == [story.id]


def test_percentages_must_come_from_a_tool(db_session):
    add_prices(db_session, "NVDA", [100.0, 102.0, 104.5])
    first, last = date.today() - timedelta(days=3), date.today()
    move = call("price_move", symbols=["nvda", "NOPE"], start=first.isoformat(), end=last.isoformat())
    model = Script([move],
                   [call("give_answer", answer="NVDA rose 7.1% and the sector 3%.", story_ids=[])],
                   [call("give_answer", answer="NVDA rose 4.5% over the period.", story_ids=[])])
    result = ask.ask("how did nvidia move", db_session, client=model)
    moves = json.loads(model.tool_results(1)[0])["moves"]
    assert moves[0]["change_pct"] == 4.5 and "fewer than two closes" in moves[1]["error"]
    assert "['7.1%', '3%']" in model.tool_results(2)[-1]
    assert result.answer.startswith("NVDA rose 4.5%") and result.unchecked == []


def test_figures_still_unsupported_after_one_refusal_are_listed_not_hidden(db_session):
    model = Script([call("give_answer", answer="Up 9%.", story_ids=[])])
    result = ask.ask("anything", db_session, client=model)
    assert result.stopped == "answered" and result.unchecked == ["9%"]


def test_buy_or_sell_advice_is_always_refused(db_session):
    model = Script([call("give_answer", answer="You should buy NVDA now.", story_ids=[])],
                   [call("give_answer", answer="I recommend selling.", story_ids=[])],
                   [call("give_answer", answer="NVDA had two earnings stories.", story_ids=[])])
    result = ask.ask("should I buy nvidia", db_session, client=model)
    assert all(t.startswith("ERROR: no investment advice") for t in model.tool_results(2))
    assert result.answer == "NVDA had two earnings stories."


def test_a_story_carries_its_moves_after_in_percent(db_session):
    story = add_article(db_session)
    db_session.add(EventOutcome(article_id=story.id, ticker="NVDA", benchmark="SPX", event_type="earnings",
                                sentiment="bullish", published_at=NOW, base_date=date.today() - timedelta(days=1),
                                day0_date=date.today(), ret_day0=0.016839, ret_1d=0.022926, ret_5d=None,
                                bench_day0=-0.007712))
    db_session.commit()
    data = json.loads(ask_tools.get_story(db_session, story.id))
    assert data["moves_after"][0]["day0_pct"] == 1.68 and data["moves_after"][0]["plus_5d_pct"] is None
    assert data["moves_after"][0]["benchmark_day0_pct"] == -0.77
    found = json.loads(ask_tools.search_stories(db_session, ticker="NVDA"))["stories"][0]
    assert found["moved_day0"] == [{"ticker": "NVDA", "day0_pct": 1.68, "benchmark_day0_pct": -0.77}]


def test_an_empty_search_says_how_old_the_data_is(db_session):
    add_article(db_session, published_at=NOW - timedelta(days=20))
    data = json.loads(ask_tools.search_stories(db_session, since=date.today().isoformat()))
    assert data["total_matching"] == 0
    assert data["newest_story_in_database"] == (NOW - timedelta(days=20)).date().isoformat()


def test_old_data_is_stated_under_the_answer(db_session):
    story = add_article(db_session, published_at=NOW - timedelta(days=20))
    model = Script([call("search_stories")], [call("give_answer", answer="One story.", story_ids=[story.id])])
    result = ask.ask("latest news", db_session, client=model)
    assert result.answer.endswith(f"The newest story in the data is from {(NOW - timedelta(days=20)).date().isoformat()}.")


def test_bad_filters_are_told_to_the_model():
    with pytest.raises(ask_tools.ToolError, match="sentiment must be one of"):
        ask_tools.search_stories(None, sentiment="negative")


def test_the_endpoint_needs_an_account_limits_each_one_and_reuses_answers(client, anon_client, db_session, monkeypatch):
    story = add_article(db_session)
    models = []

    def fake_ask(question, db):
        models.append(question)
        return ask.Result(answer="One story.", story_ids=[story.id], stopped="answered", total_matching=1)

    monkeypatch.setattr(ask, "ask", fake_ask)
    monkeypatch.setattr(settings, "ask_per_user_hour", 2)
    first = client.post("/ask", json={"question": "Nvidia news?"}).json()
    assert first["stories"][0]["id"] == story.id and not first["cached"]
    assert client.post("/ask", json={"question": "nvidia NEWS"}).json()["cached"]   # same question
    assert client.post("/ask", json={"question": "Bank news"}).status_code == 200
    assert client.post("/ask", json={"question": "Energy news"}).status_code == 429
    assert models == ["Nvidia news?", "Bank news"]
    assert client.post("/ask", json={"question": "x" * 301}).status_code == 422
    del client.headers["Authorization"]
    assert client.post("/ask", json={"question": "Nvidia news?"}).status_code == 401


def test_the_eval_checks_cited_stories_against_the_database(db_session):
    from backend import ask_evals

    bank = add_article(db_session, id_hint="a", tickers=("JPM",), sector="Financials", sentiment="bearish")
    tech = add_article(db_session, id_hint="b", tickers=("NVDA",), sector="Technology", sentiment="bearish")
    case = {"filters": {"sector": "Financials", "sentiment": "bearish"}, "cited_match": True, "states_total": True}
    steps = [{"kind": "tool", "tool": "search_stories", "failed": False,
              "arguments": json.dumps({"sector": "Financials", "sentiment": "bearish"})}]
    good = ask.Result(answer="There is 1 bearish bank story in the data.", story_ids=[bank.id], stopped="answered",
                      total_matching=1, steps=steps)
    assert all(ask_evals.check(db_session, case, good).values())
    wrong = ask.Result(answer="Two stories are in the list for banks.", story_ids=[bank.id, tech.id], stopped="answered",
                       total_matching=1, steps=steps)
    failed = {k for k, v in ask_evals.check(db_session, case, wrong).items() if not v}
    assert failed == {"cited_match", "states_total"}
