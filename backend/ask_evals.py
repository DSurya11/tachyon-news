"""
backend/ask_evals.py
────────────────────
Runs Ask the news on the cases in evals/ask_cases.yaml against the local database and the real
models, and checks every run in code. Results go to evals/results/<time>.json.

    python -m backend.ask_evals                 # all cases once
    python -m backend.ask_evals --repeat 3 --only nvidia,banks-bearish

Real model calls on free tiers: about 10 to 40 s and 5k to 30k tokens a question.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import re
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import yaml

from backend import ask, ask_tools
from backend.db import SessionLocal
from backend.routers.news import get_news

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "evals" / "ask_cases.yaml"
RESULTS = ROOT / "evals" / "results"
ENGLISH = {"the", "and", "of", "in", "a", "to", "is", "are", "no", "on", "for", "with", "stories", "story"}


def _searches(result: ask.Result) -> list[dict]:
    out = []
    for s in result.steps:
        if s["kind"] == "tool" and s["tool"] == "search_stories" and not s["failed"]:
            with contextlib.suppress(ValueError):   # a run whose arguments were not JSON
                out.append(json.loads(s["arguments"] or "{}"))
    return out


def _same(a, b) -> bool:
    return str(a).strip().lower() == str(b).strip().lower()


def check(db, case: dict, result: ask.Result) -> dict[str, bool]:
    checks = {"answered": result.stopped == "answered"}
    words = set(re.findall(r"[a-z]+", result.answer.lower()))
    checks["english"] = len(words & ENGLISH) >= 2
    checks["no_advice"] = not ask.ADVICE.search(result.answer)
    checks["numbers_from_tools"] = not result.unchecked
    searches = _searches(result)
    if want := case.get("filters"):
        checks["filters"] = any(all(_same(s.get(k), v) for k, v in want.items()) for s in searches)
        if case.get("cited_match") and result.story_ids:
            found = get_news(window=(None, None), sector=want.get("sector"), ticker=want.get("ticker"), trading_day=None,
                             q=None, market=want.get("market"), status="verified,extracted", sentiment=want.get("sentiment"),
                             event=want.get("event"), verified_only=bool(want.get("verified_only")), picks=False,
                             ids=",".join(map(str, result.story_ids)), page=1, limit=len(result.story_ids), db=db)
            checks["cited_match"] = found["total"] == len(result.story_ids)
    if case.get("states_total"):
        checks["states_total"] = result.total_matching is not None and str(result.total_matching) in result.answer
    for tool in case.get("uses", []):
        checks[f"uses_{tool}"] = any(s["kind"] == "tool" and s["tool"] == tool and not s["failed"] for s in result.steps)
    if price := case.get("price"):
        true = json.loads(ask_tools.price_move(db, **price))["moves"][0]["change_pct"]
        checks["states_price"] = any(f in result.answer for f in {f"{abs(true):.2f}", f"{abs(true):.1f}"})
    if case.get("no_stories"):
        checks["no_stories"] = result.story_ids == []
    return checks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--only", default="", help="comma-separated case ids")
    parser.add_argument("--pause", type=float, default=4.0, help="seconds between questions (free-tier rate limits)")
    args = parser.parse_args()
    cases = yaml.safe_load(CASES.read_text(encoding="utf-8"))
    if args.only:
        wanted = set(args.only.split(","))
        cases = [c for c in cases if c["id"] in wanted]
    runs, by_check = [], defaultdict(lambda: [0, 0])
    with SessionLocal() as db:
        for case in cases:
            for n in range(1, args.repeat + 1):
                result = ask.ask(case["question"], db)
                checks = check(db, case, result)
                for k, v in checks.items():
                    by_check[k][0] += int(v)
                    by_check[k][1] += 1
                ok = all(checks.values())
                model = next((s["model"] for s in reversed(result.steps) if s["kind"] == "model"), "-")
                failed = " ".join(k for k, v in checks.items() if not v)
                print(f"  {'ok  ' if ok else 'FAIL'} {case['id']:<22} #{n}  {model:<40} {result.seconds:6.1f}s  {failed}")
                runs.append({"case": case["id"], "question": case["question"], "ok": ok, "checks": checks,
                             "stopped": result.stopped, "answer": result.answer, "story_ids": result.story_ids,
                             "total_matching": result.total_matching, "unchecked": result.unchecked, "model": model,
                             "tokens": result.tokens_in + result.tokens_out, "seconds": result.seconds, "steps": result.steps})
                time.sleep(args.pause)
    passed = sum(r["ok"] for r in runs)
    print(f"\nAll checks passed in {passed}/{len(runs)} runs. Average {sum(r['tokens'] for r in runs) // max(len(runs), 1)} "
          f"tokens, {sum(r['seconds'] for r in runs) / max(len(runs), 1):.1f} s per question.\n\nby check:")
    for k, (good, total) in sorted(by_check.items()):
        print(f"  {k:<22} {good}/{total}")
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"{datetime.now(UTC).strftime('%Y-%m-%dT%H%M%SZ')}.json"
    path.write_text(json.dumps({"runs": runs, "passed": passed, "by_check": by_check}, indent=1, default=str))
    print(f"\nsaved {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
