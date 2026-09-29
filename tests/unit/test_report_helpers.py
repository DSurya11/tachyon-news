from pipeline.db.queries import MACRO_SECTOR, primary_sector, sectors_for
from pipeline.report.providers import clean_report


def test_clean_report_strips_fences_and_thinking():
    assert clean_report("<think>plan</think>\n```markdown\n## Hi\ntext\n```") == "## Hi\ntext"
    assert clean_report("## Plain") == "## Plain"


def test_sector_helpers():
    sector_of = {"NVDA": "Technology", "AMD": "Technology", "JPM": "Financials"}
    assert primary_sector(["JPM", "NVDA", "AMD"], sector_of) == "Technology"
    assert primary_sector(["XYZ"], sector_of) == MACRO_SECTOR
    assert sectors_for(["JPM", "NVDA"], sector_of) == ["Financials", "Technology"]
    assert sectors_for([], sector_of) == [MACRO_SECTOR]


def test_sector_helpers_fall_back_to_llm_sector():
    # Indian tickers are unknown to the Finviz sector map; the LLM's sector is used instead.
    assert primary_sector(["RELIANCE.NS"], {}, "Energy") == "Energy"
    assert sectors_for(["RELIANCE.NS"], {}, "Energy") == ["Energy"]
    # A known ticker sector still wins over the LLM's guess.
    assert primary_sector(["NVDA"], {"NVDA": "Technology"}, "Energy") == "Technology"
