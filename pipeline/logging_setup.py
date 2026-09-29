"""
pipeline/logging_setup.py
─────────────────────────
One place to configure logging for CLI entry points.

Logs go to a size-rotated file under LOG_DIR, so the log never grows
without bound (the old cron redirect produced a 7 MB file).  They are also
echoed to stderr when running in a terminal; under cron stderr only
carries crashes, so nothing is written twice.
"""
from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

from pipeline.config import settings

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s — %(message)s"

# Libraries that are chatty at INFO and drown out pipeline output.
_NOISY_LOGGERS = ("httpx", "httpcore", "openai", "anthropic", "yfinance", "peewee", "trafilatura")


def setup_logging(log_file: str | None = "pipeline.log", level: str | None = None) -> None:
    root = logging.getLogger()
    if getattr(root, "_stocknews_configured", False):
        return

    root.setLevel((level or settings.log_level).upper())
    formatter = logging.Formatter(LOG_FORMAT)

    if not log_file or sys.stderr.isatty():
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        root.addHandler(console)

    if log_file:
        log_dir = Path(settings.log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
    # yfinance logs every unknown symbol at ERROR ("possibly delisted"); the price stage
    # already tracks and summarises those, and the flood hid real errors.
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)

    root._stocknews_configured = True  # type: ignore[attr-defined]
