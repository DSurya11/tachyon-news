import json

from pipeline.extract.omniroute import parse_llm_response
from pipeline.extract.prompt import build_user_prompt, normalize_extraction, validate_extraction
from tests.fixtures import GOOD_EXTRACTION, GOOD_EXTRACTION_JSON


def test_parses_bare_json():
    assert parse_llm_response(GOOD_EXTRACTION_JSON) == GOOD_EXTRACTION


def test_parses_fenced_json_with_prose():
    text = f"Sure! Here it is:\n```json\n{GOOD_EXTRACTION_JSON}\n```\nLet me know."
    assert parse_llm_response(text) == GOOD_EXTRACTION


def test_ignores_think_blocks_and_reasoning_objects():
    text = (
        '<think>maybe {"tickers": ["X"]} ... </think>'
        'Reasoning: the schema is {"a": 1}. Final answer: ' + GOOD_EXTRACTION_JSON
    )
    assert parse_llm_response(text) == GOOD_EXTRACTION


def test_content_block_lists():
    blocks = [{"type": "text", "text": GOOD_EXTRACTION_JSON[:40]}, {"type": "text", "text": GOOD_EXTRACTION_JSON[40:]}]
    assert parse_llm_response(blocks) == GOOD_EXTRACTION


def test_truncated_or_empty_returns_none():
    assert parse_llm_response('{\n  "tickers":') is None
    assert parse_llm_response("") is None
    assert parse_llm_response(None) is None
    assert parse_llm_response('{"unrelated": true}') is None


def test_normalize_coerces_sloppy_output():
    data = normalize_extraction(
        {
            "tickers": ["nvda", "$AMD", "NASDAQ:INTC", "not a ticker", "NVDA"],
            "event_type": "M&A",
            "sentiment": "Slightly Bullish",
            "key_facts": "one fact",
            "numbers": [{"value": 30}, "12%", {"unit": "x"}],
            "one_line": " Summary ",
            "evidence": None,
        }
    )
    assert data["tickers"] == ["NVDA", "AMD", "INTC"]
    assert data["event_type"] == "merger"
    assert data["sentiment"] == "bullish"
    assert data["key_facts"] == ["one fact"]
    assert [n["value"] for n in data["numbers"]] == ["30", "12%"]
    assert data["one_line"] == "Summary"
    assert data["evidence"] == ""
    assert validate_extraction(data) == []


def test_unknown_enums_fall_back_to_defaults():
    data = normalize_extraction({"event_type": "partnership", "sentiment": "optimistic", "one_line": "x"})
    assert (data["event_type"], data["sentiment"]) == ("other", "neutral")


def test_validation_requires_a_summary():
    assert "one_line is empty" in validate_extraction(normalize_extraction({"sentiment": "bullish"}))


def test_user_prompt_truncates_body_and_handles_headline_only():
    assert build_user_prompt("H", "x" * 10_000, max_body_chars=100).endswith("x" * 100)
    assert "headline only" in build_user_prompt("H", None)
    json.dumps(build_user_prompt("H", "body"))  # plain string
