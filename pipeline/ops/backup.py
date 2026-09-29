"""
pipeline/ops/backup.py
──────────────────────
Dumps of the local Postgres — the only complete copy of the data (Neon holds
just the public subset; article bodies, evidence quotes and accounts live only
here). pg_dump runs inside the Docker container, so nothing needs installing on
the host. The newest BACKUP_KEEP dumps are kept; the systemd timer takes one a
day (`make deploy`), and `make restore FILE=…` brings one back.

    python -m pipeline.ops.backup            # dump now, prune old dumps
    python -m pipeline.ops.backup --list
"""
from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from pipeline.config import settings

log = logging.getLogger(__name__)

PREFIX = "stocknews-"
SUFFIX = ".dump"
MIN_BYTES = 1024  # a real dump of even an empty schema is bigger than this


def backup_dir() -> Path:
    return Path(settings.backup_dir).expanduser()


def list_backups(directory: Path | None = None) -> list[Path]:
    """Dumps, oldest first (names embed a UTC timestamp)."""
    directory = directory or backup_dir()
    return sorted(directory.glob(f"{PREFIX}*{SUFFIX}")) if directory.exists() else []


def to_prune(backups: list[Path], keep: int) -> list[Path]:
    """The dumps beyond the newest `keep` (never all of them)."""
    keep = max(keep, 1)
    return sorted(backups)[:-keep] if len(backups) > keep else []


def dump_command() -> list[str]:
    url = make_url(settings.local_db_url)
    return ["docker", "exec", settings.postgres_container, "pg_dump",
            "-U", url.username or "postgres", "-d", url.database or "stocknews", "--format=custom"]


def dump() -> Path:
    """Write a new dump atomically (a failed dump never replaces a good one). Returns its path."""
    directory = backup_dir()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{PREFIX}{datetime.now(UTC):%Y%m%d-%H%M%S}{SUFFIX}"
    partial = target.with_suffix(".partial")
    with partial.open("wb") as fh:
        proc = subprocess.run(dump_command(), stdout=fh, stderr=subprocess.PIPE, timeout=600, check=False)
    if proc.returncode != 0 or partial.stat().st_size < MIN_BYTES:
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"pg_dump failed (exit {proc.returncode}): {proc.stderr.decode(errors='replace').strip()[:300]}")
    partial.replace(target)
    return target


def run_backup() -> Path:
    path = dump()
    removed = to_prune(list_backups(), settings.backup_keep)
    for old in removed:
        old.unlink(missing_ok=True)
    log.info("Backup written: %s (%.1f MB); %d old dump(s) removed", path, path.stat().st_size / 1e6, len(removed))
    return path


def main(argv: list[str] | None = None) -> int:
    from pipeline.logging_setup import setup_logging

    setup_logging("backup.log")
    parser = argparse.ArgumentParser(description="Back up the local Postgres")
    parser.add_argument("--list", action="store_true", help="List existing dumps")
    args = parser.parse_args(argv)
    if args.list:
        for p in list_backups():
            print(f"{p}  {p.stat().st_size / 1e6:.1f} MB")
        return 0
    try:
        path = run_backup()
    except Exception as exc:  # noqa: BLE001 — any failure is reported through an alert
        log.error("Backup failed: %s", exc)
        from pipeline.ops.alerts import notify

        notify(f"✗ database backup failed: {exc}"[:300])
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
