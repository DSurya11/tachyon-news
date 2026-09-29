"""Alerts, backups, the doctor, the unattended run mode and the Claude.ai login marker."""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest

from pipeline import run_pipeline
from pipeline.config import settings
from pipeline.ops import alerts, backup, doctor

# ── alerts ─────────────────────────────────────────────────────────────────────

EMPTY = {"failures": {}, "alerted": []}


def test_one_failure_is_a_hiccup_two_in_a_row_alert():
    state, msgs = alerts.evaluate(EMPTY, {"scrape": "FAILED: timeout", "fetch": {"fetched": 3}}, threshold=2)
    assert msgs == []
    assert state["failures"] == {"scrape": 1}
    state, msgs = alerts.evaluate(state, {"scrape": "FAILED: timeout again"}, threshold=2)
    assert msgs == ["✗ scrape failed (2 runs in a row): timeout again"]
    state, msgs = alerts.evaluate(state, {"scrape": "FAILED: still"}, threshold=2)
    assert msgs == []  # no repeat while it stays broken
    state, msgs = alerts.evaluate(state, {"scrape": {"found": 90}}, threshold=2)
    assert msgs == ["✓ scrape recovered"]
    assert state == EMPTY


def test_an_unreachable_database_alerts_at_once():
    _, msgs = alerts.evaluate(EMPTY, {"schema": "FAILED: connection refused"}, threshold=2)
    assert msgs == ["✗ schema failed (run): connection refused"]


def test_after_run_keeps_state_and_pings(monkeypatch):
    sent, pings = [], []
    monkeypatch.setattr(alerts, "notify", lambda body, urgent=True: sent.append(body))
    monkeypatch.setattr(alerts, "ping_healthcheck", lambda ok, summary: pings.append((ok, summary)))
    alerts.save_state(EMPTY)
    alerts.after_run({"prices": "FAILED: yahoo down"})
    alerts.after_run({"prices": "FAILED: yahoo down"})
    assert sent == ["✗ prices failed (2 runs in a row): yahoo down"]
    assert pings == [(False, "failed: prices"), (False, "failed: prices")]
    alerts.after_run({"prices": {"rows": 10}})
    assert sent[-1] == "✓ prices recovered" and pings[-1] == (True, "ok")
    alerts.after_run({}, crashed=RuntimeError("boom"))
    assert sent[-1] == "✗ the run crashed: RuntimeError: boom"


def test_channels_are_opt_in(monkeypatch):
    posts = []
    monkeypatch.setattr(alerts.httpx, "post", lambda url, **kw: posts.append((url, kw.get("content"))))
    alerts.notify("hello")
    alerts.ping_healthcheck(True, "ok")
    assert posts == []  # nothing configured
    monkeypatch.setattr(settings, "alert_webhook_url", "https://ntfy.example/topic")
    monkeypatch.setattr(settings, "healthcheck_url", "https://hc.example/abc/")
    alerts.notify("hello")
    alerts.ping_healthcheck(False, "failed: scrape")
    assert posts == [("https://ntfy.example/topic", b"hello"), ("https://hc.example/abc/fail", b"failed: scrape")]


def test_alerting_never_raises(monkeypatch):
    monkeypatch.setattr(alerts, "load_state", lambda: 1 / 0)
    alerts.after_run({"scrape": "FAILED: x"})  # logged, not raised


# ── unattended runs ────────────────────────────────────────────────────────────

def test_unattended_run_alerts_and_exits_zero_on_stage_failures(monkeypatch):
    def broken(ctx):
        raise RuntimeError("feed down")

    monkeypatch.setattr(run_pipeline, "_stage_schema", lambda ctx: "ok")
    monkeypatch.setattr(run_pipeline, "STAGES", {"scrape": ("M1", broken), "fetch": ("M2", lambda ctx: {"n": 1})})
    seen = []
    monkeypatch.setattr(alerts, "after_run", lambda results, crashed=None: seen.append((dict(results), crashed)))
    assert run_pipeline.main([]) == 1  # interactive: the failure shows in the exit code
    assert seen == []
    assert run_pipeline.main(["--unattended"]) == 0  # scheduled: alerts carry it instead
    assert seen == [({"scrape": "FAILED: feed down", "fetch": {"n": 1}}, None)]


def test_unattended_crash_alerts_and_still_fails(monkeypatch):
    monkeypatch.setattr(run_pipeline, "run", lambda *a, **k: (_ for _ in ()).throw(MemoryError("oom")))
    seen = []
    monkeypatch.setattr(alerts, "after_run", lambda results, crashed=None: seen.append(crashed))
    with pytest.raises(MemoryError):
        run_pipeline.main(["--unattended"])
    assert isinstance(seen[0], MemoryError)


# ── backups ────────────────────────────────────────────────────────────────────

def test_prune_keeps_the_newest(tmp_path):
    files = [tmp_path / f"stocknews-2026092{i}-000000.dump" for i in range(5)]
    assert backup.to_prune(files, keep=3) == files[:2]
    assert backup.to_prune(files, keep=10) == []
    assert backup.to_prune(files, keep=0) == files[:4]  # never deletes every dump


def test_dump_command_uses_the_database_url(monkeypatch):
    monkeypatch.setattr(settings, "local_db_url", "postgresql://alice:pw@localhost:5432/mydb")
    monkeypatch.setattr(settings, "postgres_container", "pg")
    assert backup.dump_command() == ["docker", "exec", "pg", "pg_dump", "-U", "alice", "-d", "mydb", "--format=custom"]


def _fake_pg_dump(payload: bytes, code: int = 0):
    def run(cmd, stdout, stderr, timeout, check):
        stdout.write(payload)
        return subprocess.CompletedProcess(cmd, code, stderr=b"pg_dump: error" if code else b"")
    return run


def test_backup_writes_atomically_and_prunes(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path))
    monkeypatch.setattr(settings, "backup_keep", 2)
    for i in range(3):
        (tmp_path / f"stocknews-2026010{i}-000000.dump").write_bytes(b"x" * 2000)
    monkeypatch.setattr(backup.subprocess, "run", _fake_pg_dump(b"PGDMP" + b"x" * 5000))
    path = backup.run_backup()
    assert path.exists() and path.read_bytes().startswith(b"PGDMP")
    assert [p.name for p in backup.list_backups()] == ["stocknews-20260102-000000.dump", path.name]
    assert not list(tmp_path.glob("*.partial"))


@pytest.mark.parametrize(("payload", "code"), [(b"PGDMP" + b"x" * 5000, 1), (b"tiny", 0)])
def test_a_failed_dump_leaves_nothing_behind(monkeypatch, tmp_path, payload, code):
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path))
    monkeypatch.setattr(backup.subprocess, "run", _fake_pg_dump(payload, code))
    with pytest.raises(RuntimeError, match="pg_dump failed"):
        backup.dump()
    assert list(tmp_path.iterdir()) == []


# ── doctor ─────────────────────────────────────────────────────────────────────

def test_doctor_backup_age(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path))
    assert doctor.check_backups().status == doctor.FAIL
    dump = tmp_path / "stocknews-20260101-000000.dump"
    dump.write_bytes(b"x")
    assert doctor.check_backups().status == doctor.OK
    old = time.time() - 5 * 86400
    os.utime(dump, (old, old))
    assert doctor.check_backups().status == doctor.FAIL


def test_doctor_release_notices_undeployed_changes(monkeypatch, tmp_path):
    monkeypatch.setattr(doctor, "DEPLOY_DIR", tmp_path)
    assert doctor.check_release().status == doctor.WARN  # nothing deployed
    (tmp_path / "release").mkdir()
    stamp = tmp_path / "release" / "RELEASE"
    stamp.write_text("2026-09-29 10:00:00 abc123")
    os.utime(stamp, (time.time() + 3600, time.time() + 3600))  # deployed after every source edit
    assert doctor.check_release().status == doctor.OK
    os.utime(stamp, (0, 0))
    check = doctor.check_release()
    assert check.status == doctor.WARN and "not deployed" in check.detail


def test_a_crashing_check_is_reported_not_raised(monkeypatch):
    monkeypatch.setattr(doctor, "CHECKS", [lambda: 1 / 0])
    [check] = doctor.run_checks()
    assert check.status == doctor.FAIL and "crashed" in check.detail


# ── Claude.ai login marker ─────────────────────────────────────────────────────

def test_expired_claude_login_is_skipped_in_unattended_runs(monkeypatch):
    from pipeline.report import claude_web, providers

    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setattr(providers.sys.stdin, "isatty", lambda: False)
    claude_web._set_login_required(True)
    assert claude_web.login_required()
    assert Path(settings.log_dir, ".claude_login_required").exists()
    with pytest.raises(providers.ProviderUnavailable, match="make claude-login"):
        providers.generate_with_claude_web(None)
    claude_web._set_login_required(False)
    assert not claude_web.login_required()


def test_a_shutdown_mid_run_stops_cleanly_without_a_crash_alert(monkeypatch):
    import signal

    def killed(ctx):
        os.kill(os.getpid(), signal.SIGTERM)  # what systemd sends at shutdown
        time.sleep(5)  # never reached: the handler interrupts it

    ran = []
    monkeypatch.setattr(run_pipeline, "_stage_schema", lambda ctx: "ok")
    monkeypatch.setattr(run_pipeline, "STAGES", {"scrape": ("M1", killed), "sync": ("M6", lambda ctx: ran.append(1))})
    alerted = []
    monkeypatch.setattr(alerts, "after_run", lambda results, crashed=None: alerted.append(crashed))
    before = signal.getsignal(signal.SIGTERM)
    assert run_pipeline.main(["--unattended"]) == 0
    assert ran == [] and alerted == []  # stopped at once, not reported as a crash
    assert signal.getsignal(signal.SIGTERM) is before  # handler restored
    with run_pipeline.run_lock():  # and the lock was released
        pass


def test_deploy_never_stops_everything():
    """`make down` stops Postgres; deploying once called it and left the site without a database."""
    from pipeline.config import PROJECT_ROOT

    makefile = (PROJECT_ROOT / "Makefile").read_text()
    recipe = makefile.split("\ninstall-services:", 1)[1].split("\n\n", 1)[0]
    assert "dev-down" in recipe
    assert " down " not in recipe.replace("dev-down", "") and "stop.sh" not in recipe
