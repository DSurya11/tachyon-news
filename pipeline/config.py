"""
pipeline/config.py
──────────────────
Typed configuration loaded from the environment (via .env).
Import `settings` anywhere in the pipeline:

    from pipeline.config import settings

All fields are validated by pydantic-settings on first import.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import AnyUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Single source of truth for all runtime configuration."""

    model_config = SettingsConfigDict(
        # Look for .env in the project root (two levels up from this file)
        env_file=str(Path(__file__).resolve().parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",          # silently ignore unknown env vars
        case_sensitive=False,    # env var names are case-insensitive
    )

    # ------------------------------------------------------------------
    # Local PostgreSQL (Docker)
    # ------------------------------------------------------------------
    local_db_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/stocknews",
        description="SQLAlchemy DSN for the local Postgres 16 instance.",
    )

    # ------------------------------------------------------------------
    # Neon (write-only from laptop)
    # ------------------------------------------------------------------
    neon_db_url: str = Field(
        default="",
        description="SQLAlchemy DSN for the Neon cloud database (write access).",
    )

    # ------------------------------------------------------------------
    # Finnhub
    # ------------------------------------------------------------------
    finnhub_api_key: str = Field(
        default="",
        description="Finnhub API key — backend-only, never exposed publicly.",
    )

    # ------------------------------------------------------------------
    # OmniRoute (local LLM router)
    # ------------------------------------------------------------------
    omniroute_base_url: str = Field(
        default="http://localhost:20128/v1",
        description="Base URL for the local OmniRoute OpenAI-compat server.",
    )
    omniroute_model: str = Field(
        default="extraction-combo",
        description="OmniRoute combo name to use for LLM extraction.",
    )

    # ------------------------------------------------------------------
    # Claude.ai Playwright
    # ------------------------------------------------------------------
    chrome_profile_dir: str = Field(
        default="/home/surya/.config/google-chrome/Default",
        description="Path to the persistent Chrome profile used for Claude.ai.",
    )
    claude_url: str = Field(
        default="https://claude.ai",
        description="Claude.ai URL (do not change unless domain changes).",
    )

    # ------------------------------------------------------------------
    # Backend / CORS
    # ------------------------------------------------------------------
    vercel_url: str = Field(
        default="https://your-app.vercel.app",
        description="Vercel deployment URL for CORS allow-list.",
    )
    api_port: int = Field(
        default=8000,
        description="Port the FastAPI server listens on.",
    )

    # ------------------------------------------------------------------
    # Readiness Gate thresholds
    # ------------------------------------------------------------------
    gate_min_days: int = Field(
        default=60,
        description="Minimum calendar days of coverage required.",
    )
    gate_max_gap_days: int = Field(
        default=3,
        description="Maximum consecutive days with no data before gate fails.",
    )
    gate_min_articles_per_sector_day: int = Field(
        default=3,
        description="Minimum usable articles per sector-day.",
    )
    gate_min_sectors: int = Field(
        default=5,
        description="Minimum number of sectors meeting the per-day threshold.",
    )
    gate_min_extracted_per_sector: int = Field(
        default=100,
        description="Minimum extracted+verified articles per sector total.",
    )


# Module-level singleton — import this everywhere.
settings = Settings()
