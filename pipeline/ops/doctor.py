"""
pipeline/ops/doctor.py
──────────────────────
`make doctor`: checks everything the unattended setup depends on and says how
to fix what isn't right. Exit code 1 when anything is broken.

    python -m pipeline.ops.doctor
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from sqlalchemy import create_engine, text

from pipeline.config import PROJECT_ROOT, settings

OK, WARN, FAIL = "ok", "warn", "fail"
MARK = {OK: "✓", WARN: "!", FAIL: "✗"}
DEPLOY_DIR = Path(os.environ.get("DEPLOY_DIR", Path.home() / ".local" / "share" / "stock-news-pipeline"))
BACKEND_PORT = int(os.environ.get("BACKEND_PORT", "8080"))
FRONTEND_PORT = int(os.environ.get("FRONTEND_PORT", "3000"))


@dataclass
class Check:
    name: str
    status: str
    detail: str
    hint: str = ""


def _age(ts: datetime) -> str:
    minutes = int((datetime.now(UTC) - ts).total_seconds() // 60)
    return f"{minutes} min ago" if minutes < 120 else f"{minutes // 60} h ago"


PLACEHOLDER = re.compile(r"<[^>]*>|\bpaste\b|changeme|your[_-]", re.I)


def check_env() -> Check:
    env = PROJECT_ROOT / ".env"
    if not env.exists():
        return Check(".env", FAIL, "missing", "cp .env.example .env and fill it in")
    # A template value left in place (ASK_API_KEY=<copy …> broke Ask on 2026-10-26).
    unfilled = []
    for line in env.read_text(encoding="utf-8").splitlines():
        name, sep, value = line.partition("=")
        if sep and not line.lstrip().startswith("#") and PLACEHOLDER.search(value):
            unfilled.append(name.strip())
    if unfilled:
        return Check(".env", WARN, f"placeholder value in {', '.join(unfilled)}", "put the real values in .env")
    return Check(".env", OK, str(env))


def check_database() -> Check:
    from pipeline.db.schema import missing_tables

    try:
        engine = create_engine(settings.local_db_url, connect_args={"connect_timeout": 5})
        missing = missing_tables(engine)
        engine.dispose()
    except Exception as exc:  # noqa: BLE001 — any connection error is the finding
        return Check("local database", FAIL, f"unreachable: {exc.__class__.__name__}", "make db-up")
    if missing:
        return Check("local database", FAIL, f"missing tables: {', '.join(sorted(missing))}", "make migrate")
    return Check("local database", OK, "reachable, schema complete")


def check_omniroute() -> Check:
    url = settings.omniroute_api_url.rstrip("/") + "/models"
    try:
        resp = httpx.get(url, headers={"Authorization": f"Bearer {settings.omniroute_api_key}"}, timeout=5)
    except Exception as exc:  # noqa: BLE001
        return Check("OmniRoute", FAIL, f"unreachable at {settings.omniroute_api_url} ({exc.__class__.__name__})",
                     "make up")
    if resp.status_code in (401, 403):
        return Check("OmniRoute", FAIL, f"key rejected ({resp.status_code})", "OMNIROUTE_API_KEY in .env")
    try:
        resp.raise_for_status()
        models = {m.get("id") for m in resp.json().get("data", [])}
    except Exception as exc:  # noqa: BLE001
        return Check("OmniRoute", FAIL, f"answered {resp.status_code} at {settings.omniroute_api_url} "
                     f"({exc.__class__.__name__})", "make up")
    if models and settings.omniroute_model not in models:
        return Check("OmniRoute", WARN, f"running, but model '{settings.omniroute_model}' is not listed",
                     "create the combo in the OmniRoute dashboard (:20128)")
    return Check("OmniRoute", OK, f"running, {len(models)} models")


def check_ask() -> Check:
    """Ask the news: the model endpoint answers, accepts the key and offers ASK_MODEL."""
    base = (settings.ask_api_url or settings.omniroute_api_url).rstrip("/")
    key = settings.ask_api_key or settings.omniroute_api_key
    try:
        resp = httpx.get(base + "/models", headers={"Authorization": f"Bearer {key}"}, timeout=5)
    except Exception as exc:  # noqa: BLE001
        return Check("Ask model", FAIL, f"unreachable at {base} ({exc.__class__.__name__})",
                     "start the router ASK_API_URL points at")
    if resp.status_code in (401, 403):
        return Check("Ask model", FAIL, f"key rejected ({resp.status_code}) at {base}", "ASK_API_KEY in .env")
    if resp.status_code != 200:
        return Check("Ask model", FAIL, f"{base} answered {resp.status_code}", "")
    models = {m.get("id") for m in resp.json().get("data", [])}
    if models and settings.ask_model not in models:
        return Check("Ask model", FAIL, f"no model '{settings.ask_model}' at {base}",
                     "create that combo, or set ASK_MODEL to one that exists")
    return Check("Ask model", OK, f"{settings.ask_model} at {base}")


def check_neon() -> Check:
    if not settings.neon_db_url:
        return Check("Neon sync", WARN, "NEON_DB_URL not set: the hosted dashboard gets no data", "")
    try:
        args = {"sslmode": "require"} if "neon.tech" in settings.neon_db_url else {}
        engine = create_engine(settings.neon_db_url, connect_args={"connect_timeout": 10, **args})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
    except Exception as exc:  # noqa: BLE001
        return Check("Neon sync", FAIL, f"unreachable: {exc.__class__.__name__}", "check NEON_DB_URL")
    return Check("Neon sync", OK, "reachable")


def check_report_providers() -> Check:
    chain = settings.report_provider_list
    usable, notes = [], []
    for name in chain:
        if name == "anthropic":
            (usable if settings.anthropic_api_key else notes).append("anthropic" if settings.anthropic_api_key else "anthropic: no key")
        elif name == "claude_web":
            from pipeline.report.claude_web import login_required

            if login_required():
                notes.append("claude_web: logged out")
            else:
                usable.append("claude_web")
        else:
            usable.append(name)
    if not usable:
        return Check("report writers", FAIL, "; ".join(notes) or "none configured", "make claude-login or set ANTHROPIC_API_KEY")
    status = WARN if notes else OK
    hint = "make claude-login" if "claude_web: logged out" in notes else ""
    return Check("report writers", status, f"usable: {', '.join(usable)}" + (f" ({'; '.join(notes)})" if notes else ""), hint)


def check_quotes() -> Check:
    if settings.finnhub_api_key:
        return Check("live quotes", OK, "Finnhub key set")
    return Check("live quotes", WARN, "no FINNHUB_API_KEY: quotes fall back to the last daily close", "")


def _systemctl(*args: str) -> str:
    if not shutil.which("systemctl"):
        return ""
    proc = subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True, timeout=10, check=False)
    return proc.stdout.strip()


def check_scheduler() -> Check:
    if _systemctl("is-active", "stocknews-pipeline.timer") == "active":
        nxt = _systemctl("show", "stocknews-pipeline.timer", "-p", "NextElapseUSecRealtime", "--value")
        return Check("scheduler", OK, f"systemd timer active (next: {nxt or '?'})")
    cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True, check=False).stdout if shutil.which("crontab") else ""
    if "stock-news-pipeline" in cron:
        return Check("scheduler", WARN, "cron job (runs the live working tree; misses runs while asleep)", "make deploy")
    return Check("scheduler", FAIL, "no scheduled job", "make deploy")


def check_last_run() -> Check:
    log = Path(settings.log_dir) / "pipeline.log"
    last = None
    try:
        for line in log.read_text(errors="replace").splitlines()[-3000:]:
            if "Pipeline finished" in line:
                last = line
    except OSError:
        pass
    if last is None:
        return Check("last run", FAIL, "no finished run in pipeline.log", "make run-pipeline")
    ts = datetime.strptime(last[:19], "%Y-%m-%d %H:%M:%S").astimezone(UTC)
    from pipeline.ops.alerts import load_state

    failures = load_state().get("failures", {})
    detail = f"{_age(ts)}; " + last.split("Pipeline finished ", 1)[1]
    if failures:
        detail += f"; failing: {', '.join(f'{k}×{v}' for k, v in failures.items())}"
    age = datetime.now(UTC) - ts
    status = OK if age < timedelta(hours=2) and not failures else WARN if age < timedelta(hours=6) else FAIL
    return Check("last run", status, detail, "journalctl --user -u stocknews-pipeline -e" if status != OK else "")


def _http_ok(url: str, timeout: float = 5) -> bool:
    try:
        return httpx.get(url, timeout=timeout).status_code < 500
    except httpx.HTTPError:
        return False


# Measured 2026-10-26: from this laptop the Funnel URL took 3 to 17 s (the API itself ~10 ms), and
# the 5 s limit reported a working tunnel as down. Same limit as the dashboard's first contact.
PUBLIC_TIMEOUT_S = 20


def check_services() -> Check:
    api = _http_ok(f"http://127.0.0.1:{BACKEND_PORT}/health")
    dash = _http_ok(f"http://127.0.0.1:{FRONTEND_PORT}/")
    if api and dash:
        return Check("API + dashboard", OK, f":{BACKEND_PORT} and :{FRONTEND_PORT} responding")
    down = [n for n, up in (("API", api), ("dashboard", dash)) if not up]
    return Check("API + dashboard", FAIL, f"not responding: {', '.join(down)}", "make up")


def check_public() -> Check:
    """The hosted dashboard and the tunnel it reaches the API through, seen from outside."""
    if not settings.public_api_url and not settings.public_site_url:
        return Check("public access", WARN, "PUBLIC_API_URL / PUBLIC_SITE_URL not set: the hosted dashboard isn't checked", "")
    down = [f"{name} ({url})" for name, url in (("tunnel", f"{settings.public_api_url.rstrip('/')}/health"),
                                                ("site", settings.public_site_url))
            if url and url != "/health" and not _http_ok(url, PUBLIC_TIMEOUT_S)]
    if down:
        return Check("public access", FAIL, f"not reachable: {', '.join(down)}",
                     "tailscale up; tailscale funnel --bg 8080 (make up does both)")
    return Check("public access", OK, " · ".join(u for u in (settings.public_site_url, settings.public_api_url) if u))


def check_disk() -> Check:
    free_gb = shutil.disk_usage(Path.home()).free / 1e9
    status = OK if free_gb > 5 else WARN if free_gb > 1 else FAIL
    return Check("disk", status, f"{free_gb:.0f} GB free")


def check_release() -> Check:
    release = DEPLOY_DIR / "release"
    stamp = release / "RELEASE"
    if PROJECT_ROOT.resolve() == release.resolve():
        return Check("release", OK, "running from the deployed release")
    if not stamp.exists():
        return Check("release", WARN, "nothing deployed: scheduled runs would use the working tree", "make deploy")
    deployed = stamp.stat().st_mtime
    sources = [p for d in ("pipeline", "backend", "frontend/tachyon-news/src") for p in (PROJECT_ROOT / d).rglob("*")
               if p.suffix in (".py", ".ts", ".tsx", ".css") and p.is_file()]
    newer = [p for p in sources if p.stat().st_mtime > deployed]
    if newer:
        return Check("release", WARN, f"{len(newer)} changed file(s) not deployed yet ({stamp.read_text().strip()})",
                     "make deploy when you're happy with them")
    return Check("release", OK, stamp.read_text().strip())


CHECKS: list[Callable[[], Check]] = [
    check_env, check_database, check_omniroute, check_ask, check_neon, check_report_providers, check_quotes,
    check_scheduler, check_last_run, check_services, check_public, check_disk, check_release,
]


def run_checks() -> list[Check]:
    results = []
    for fn in CHECKS:
        try:
            results.append(fn())
        except Exception as exc:  # noqa: BLE001 — a broken check is itself a finding
            results.append(Check(fn.__name__.removeprefix("check_"), FAIL, f"check crashed: {exc}"))
    return results


def main() -> int:
    results = run_checks()
    width = max(len(c.name) for c in results)
    for c in results:
        print(f" {MARK[c.status]} {c.name:<{width}}  {c.detail}" + (f"\n   {'':<{width}}  → {c.hint}" if c.hint else ""))
    failing = sum(c.status == FAIL for c in results)
    print(f"\n{failing} problem(s), {sum(c.status == WARN for c in results)} warning(s)")
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
