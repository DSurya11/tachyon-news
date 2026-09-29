from pipeline.report.top_picks import split_top_picks

REPORT = "## Market Overview\nStocks rose [1].\n\n## What to Watch\n- CPI [2]"


def test_fenced_block_is_removed_and_validated():
    content = REPORT + '\n\n```json\n{"top_picks": [{"id": 2, "why": "CPI  sets\\nthe tone"}, {"id": 99, "why": "unknown id"},' \
        ' {"id": 2, "why": "duplicate"}, {"id": "1", "why": "string id"}]}\n```\n'
    body, picks = split_top_picks(content, [1, 2], limit=10)
    assert body == REPORT
    assert picks == [{"id": 2, "rank": 1, "why": "CPI sets the tone"}, {"id": 1, "rank": 2, "why": "string id"}]


def test_bare_object_without_fence_and_label_line():
    # Claude.ai's copied text can lose the code fence and keep a "json" label.
    content = REPORT + '\n\njson\n{"top_picks": [{"id": 1, "why": "x"}]}'
    body, picks = split_top_picks(content, [1], limit=10)
    assert body == REPORT and [p["id"] for p in picks] == [1]


def test_limit_and_missing_block():
    content = REPORT + '\n```json\n{"top_picks": [{"id": 1}, {"id": 2}]}\n```'
    assert [p["id"] for p in split_top_picks(content, [1, 2], limit=1)[1]] == [1]
    assert split_top_picks(REPORT, [1, 2], limit=5) == (REPORT, [])
    assert split_top_picks(REPORT + '\n```json\n{"top_picks": nope}\n```', [1], 5)[1] == []
