"""
pipeline/ops/alerts.py
──────────────────────
Tells you when the scheduled pipeline needs attention, without nagging.

A stage failing once is usually a hiccup (a feed timing out, a rate limit), so
an alert goes out when the same stage fails ALERT_AFTER_FAILURES runs in a row,
and a "recovered" note when it next succeeds. A crashed run, or a database that
can't be reached, alerts at once.

Channels — each optional; a channel that fails is logged and skipped:
  - desktop notification (notify-send, from the systemd user session)
  - ALERT_WEBHOOK_URL: the message as a plain-text POST, e.g. an ntfy.sh topic
    for pushes to your phone
  - HEALTHCHECK_URL: a dead-man's switch pinged after every run
    (healthchecks.io style: <url> on success, <url>/fail on failure), so you
    also hear about runs that never happen — laptop off, scheduler broken

State lives in LOG_DIR/.alert_state.json.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

import httpx

from pipeline.config import settings

log = logging.getLogger(__name__)

TITLE = "Stock-news pipeline"
IMMEDIATE = frozenset({"schema"})  # database unreachable: no point waiting for a second run
TIMEOUT_S = 10


def _state_path() -> Path:
    return Path(settings.log_dir) / ".alert_state.json"


def load_state() -> dict:
    try:
        return json.loads(_state_path().read_text())
    except (OSError, ValueError):
        return {"failures": {}, "alerted": []}


def save_state(state: dict) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True))
    tmp.replace(path)


def failed(result: object) -> bool:
    return isinstance(result, str) and result.startswith("FAILED")


def evaluate(state: dict, results: dict[str, object], threshold: int) -> tuple[dict, list[str]]:
    """
    Fold one run's stage results into the alert state.
    Returns (new state, messages to send). Pure: no I/O.
    """
    failures = dict(state.get("failures") or {})
    alerted = set(state.get("alerted") or [])
    messages: list[str] = []
    for stage, result in results.items():
        if failed(result):
            failures[stage] = failures.get(stage, 0) + 1
            limit = 1 if stage in IMMEDIATE else max(threshold, 1)
            if failures[stage] >= limit and stage not in alerted:
                runs = "run" if failures[stage] == 1 else f"{failures[stage]} runs in a row"
                messages.append(f"✗ {stage} failed ({runs}): {str(result)[len('FAILED: '):][:200]}")
                alerted.add(stage)
        else:
            failures.pop(stage, None)
            if stage in alerted:
                messages.append(f"✓ {stage} recovered")
                alerted.discard(stage)
    return {"failures": failures, "alerted": sorted(alerted)}, messages


def _desktop(body: str, urgent: bool) -> None:
    if not settings.alert_desktop or not shutil.which("notify-send"):
        return
    try:
        subprocess.run(
            ["notify-send", "--app-name=stock-news", "-u", "critical" if urgent else "normal", TITLE, body],
            timeout=TIMEOUT_S, check=False, capture_output=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log.info("Desktop notification failed: %s", exc)


def _webhook(body: str, urgent: bool) -> None:
    if not settings.alert_webhook_url:
        return
    try:
        httpx.post(settings.alert_webhook_url, content=body.encode(), timeout=TIMEOUT_S,
                   headers={"Title": TITLE, "Priority": "high" if urgent else "default"})
    except httpx.HTTPError as exc:
        log.info("Alert webhook failed: %s", exc)


def notify(body: str, urgent: bool = True) -> None:
    log.warning("ALERT: %s", body)
    _desktop(body, urgent)
    _webhook(body, urgent)


def ping_healthcheck(ok: bool, summary: str) -> None:
    if not settings.healthcheck_url:
        return
    url = settings.healthcheck_url.rstrip("/") + ("" if ok else "/fail")
    try:
        httpx.post(url, content=summary.encode()[:10_000], timeout=TIMEOUT_S)
    except httpx.HTTPError as exc:
        log.info("Healthcheck ping failed: %s", exc)


def after_run(results: dict[str, object], crashed: BaseException | None = None) -> None:
    """Called after every scheduled run. Never raises."""
    try:
        if crashed is not None:
            notify(f"✗ the run crashed: {type(crashed).__name__}: {crashed}"[:300])
            ping_healthcheck(False, f"crashed: {crashed!r}")
            return
        state, messages = evaluate(load_state(), results, settings.alert_after_failures)
        save_state(state)
        for message in messages:
            notify(message, urgent=message.startswith("✗"))
        bad = [k for k, v in results.items() if failed(v)]
        ping_healthcheck(not bad, "failed: " + ", ".join(bad) if bad else "ok")
    except Exception as exc:  # alerting must never break the pipeline
        log.error("Alerting failed: %s", exc, exc_info=True)
