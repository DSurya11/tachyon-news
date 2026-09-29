"""Story outcomes and the priced-in verdict: session placement, horizons, and history gating."""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from backend.reaction import verdict
from pipeline.prices.outcomes import Series, outcome

NY = ZoneInfo("America/New_York")
DAYS = [date(2026, 9, d) for d in (21, 22, 23, 24, 25, 28, 29, 30)] + [date(2026, 10, 1)]
STOCK = Series(DAYS, [100, 100, 110, 111, 112, 113, 114, 115, 116])
BENCH = Series(DAYS, [50, 50, 51, 51, 51, 51, 51, 51, 51])
LATER = datetime(2026, 10, 2, 12, tzinfo=NY)


def test_during_the_session_measures_from_the_previous_close():
    r = outcome(datetime(2026, 9, 23, 11, tzinfo=NY), STOCK, BENCH, "SPX", LATER)
    assert r["base_date"] == date(2026, 9, 22) and r["day0_date"] == date(2026, 9, 23)
    assert round(r["ret_day0"], 4) == 0.10 and round(r["bench_day0"], 4) == 0.02
    assert round(r["ret_1d"], 4) == 0.11 and round(r["ret_5d"], 4) == 0.15  # 5 sessions on, across the weekend


def test_after_the_close_the_next_session_is_day_zero():
    r = outcome(datetime(2026, 9, 22, 17, tzinfo=NY), STOCK, BENCH, "SPX", LATER)
    assert r["base_date"] == date(2026, 9, 22) and r["day0_date"] == date(2026, 9, 23)


def test_horizons_wait_for_their_close():
    early = datetime(2026, 9, 24, 15, tzinfo=NY)  # Sep 24 not closed yet: its row is a live price
    r = outcome(datetime(2026, 9, 23, 11, tzinfo=NY), STOCK, BENCH, "SPX", early)
    assert r["ret_day0"] is not None and r["ret_1d"] is None and r["ret_5d"] is None
    assert outcome(datetime(2026, 9, 24, 11, tzinfo=NY), STOCK, BENCH, "SPX", early) is None


def test_no_close_before_the_headline_means_no_outcome():
    assert outcome(datetime(2026, 9, 21, 10, tzinfo=NY), STOCK, BENCH, "SPX", LATER) is None


def test_missing_benchmark_leaves_bench_empty():
    r = outcome(datetime(2026, 9, 23, 11, tzinfo=NY), STOCK, None, "SPX", LATER)
    assert r["bench_day0"] is None and r["ret_day0"] is not None


def test_verdict_describes_how_much_of_the_usual_move_happened():
    hist = {"horizon": "5d", "median": -2.8}
    assert verdict(-2.5, hist) == "mostly"
    assert verdict(-1.0, hist) == "partly"
    assert verdict(-0.3, hist) == "little"
    assert verdict(+1.2, hist) == "against"
    assert verdict(-2.5, {"horizon": "5d", "median": 0.2}) == "usually_small"
    assert verdict(-2.5, {"horizon": None}) is None and verdict(None, hist) is None
