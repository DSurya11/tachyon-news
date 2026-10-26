"""
pipeline/config.py
──────────────────
Typed configuration loaded from the environment (via .env).
Import `settings` anywhere in the pipeline:

    from pipeline.config import settings

Real environment variables always win over values in .env.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# "your-app": an earlier template's VERCEL_URL=https://your-app.vercel.app. Left in a .env, it was
# added to the API's allowed origins, and that address is one anybody can register.
_PLACEHOLDER_MARKERS = ("CHANGEME", "your_", "your-app", "ep-xxx")


def _is_placeholder(value: str) -> bool:
    return any(marker in value for marker in _PLACEHOLDER_MARKERS)


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings(BaseSettings):
    """Single source of truth for all runtime configuration."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ------------------------------------------------------------------
    # Databases
    # ------------------------------------------------------------------
    local_db_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/stocknews",
        description="SQLAlchemy DSN for the local Postgres instance (full dataset).",
    )
    neon_db_url: str = Field(
        default="",
        description="SQLAlchemy DSN for the Neon cloud database (write access, laptop only).",
    )
    api_db_url: str = Field(
        default="",
        description="DSN the FastAPI backend reads from. Falls back to NEON_DB_URL, then LOCAL_DB_URL.",
    )
    neon_sync_lookback_days: int = Field(
        default=3,
        description="Incremental Neon sync window. Rows touched within this many days are re-synced.",
    )
    neon_sync_chunk_size: int = Field(default=500, description="Rows per INSERT when syncing to Neon.")
    auth_db_url: str = Field(
        default="",
        description="DSN for user accounts (needs write access to users/user_sessions). Falls back to the API DSN.",
    )

    # ------------------------------------------------------------------
    # Finnhub (live quotes in the API)
    # ------------------------------------------------------------------
    finnhub_api_key: str = Field(default="", description="Finnhub API key — backend-only.")

    # ------------------------------------------------------------------
    # India market (RSS feeds; Finviz covers US-listed stocks only)
    # ------------------------------------------------------------------
    india_feeds: str = Field(
        default=(
            "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms,"
            "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms,"
            "https://www.livemint.com/rss/markets,"
            "https://www.business-standard.com/rss/markets-106.rss"
        ),
        description="Comma-separated RSS feeds for Indian market news. Empty = India stage off.",
    )
    india_max_age_hours: int = Field(default=72, description="Ignore feed items older than this.")

    # ------------------------------------------------------------------
    # Body fetch
    # ------------------------------------------------------------------
    fetch_skip_domains: str = Field(
        default="wsj.com,barrons.com,marketwatch.com,ft.com,bloomberg.com,investors.com",
        description="Comma-separated hard-paywall domains; bodies are not fetched for these.",
    )
    fetch_max_per_run: int = Field(default=400, description="Upper bound on bodies fetched per run.")

    # ------------------------------------------------------------------
    # OmniRoute (local OpenAI-compatible LLM router)
    # ------------------------------------------------------------------
    # Deliberately not OMNIROUTE_BASE_URL: the omniroute CLI reads this project's
    # .env too and uses that name for its dashboard (:20128), not the API (:8000).
    omniroute_api_url: str = Field(
        default="http://localhost:8000/v1",
        description="OpenAI-compatible inference endpoint exposed by OmniRoute (the 'API Base' it prints).",
    )
    omniroute_api_key: str = Field(default="my-secret-key", description="API key configured in OmniRoute.")
    omniroute_model: str = Field(default="extraction-combo", description="OmniRoute combo used for extraction.")
    omniroute_report_model: str = Field(
        default="",
        description="OmniRoute combo used for the report fallback (defaults to OMNIROUTE_MODEL).",
    )
    omniroute_timeout_s: float = Field(default=90.0)
    omniroute_json_mode: bool = Field(
        default=True,
        description="Send response_format=json_object. Disabled automatically if the router rejects it.",
    )

    # Ask the news (backend/ask.py): an agent with tool calls, so a combo of models that do them.
    ask_api_url: str = Field(default="", description="OpenAI-compatible endpoint for Ask (default: OMNIROUTE_API_URL).")
    ask_api_key: str = Field(default="", description="Key for that endpoint (default: OMNIROUTE_API_KEY).")
    ask_model: str = Field(default="ask-combo", description="A combo of tool-calling models, e.g. gpt-oss-120b → gpt-oss-20b.")
    ask_per_user_hour: int = Field(default=10, description="Ask questions one account may send per hour.")
    ask_daily_total: int = Field(default=200, description="Ask questions all accounts together may send per day.")

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------
    extraction_max_per_run: int = Field(default=150, description="Cap on LLM extractions per pipeline run.")
    extraction_concurrency: int = Field(
        default=3,
        description="Parallel extraction workers (keep low for free-tier rate limits).",
    )
    extraction_max_attempts: int = Field(default=3, description="Attempts before an article is given up on.")
    extraction_max_body_chars: int = Field(default=4000, description="Body characters sent to the LLM.")
    extraction_max_consecutive_errors: int = Field(
        default=5,
        description="Abort the extraction stage after this many back-to-back API/connection errors.",
    )

    # ------------------------------------------------------------------
    # Daily report
    # ------------------------------------------------------------------
    report_providers: str = Field(
        default="anthropic,claude_web,omniroute",
        description="Ordered, comma-separated provider chain. First one that succeeds wins.",
    )
    report_min_articles: int = Field(default=5, description="Minimum usable articles before a report is written.")
    report_refresh_new_articles: int = Field(
        default=15,
        description="Regenerate an existing report once this many new articles have arrived.",
    )
    report_max_articles_per_sector: int = Field(default=15)
    report_top_picks: int = Field(
        default=15,
        description="How many must-read stories the report writer ranks (the dashboard's 'Top picks').",
    )
    report_max_prompt_chars: int = Field(
        default=30000,
        description="Budget for the article data in the report prompt (~7.5k tokens).",
    )
    anthropic_api_key: str = Field(default="", description="Enables the 'anthropic' report provider.")
    anthropic_model: str = Field(default="claude-opus-5")

    # Claude.ai browser automation (the 'claude_web' provider)
    chrome_profile_dir: str = Field(
        default=str(Path.home() / ".config" / "stock-news-pipeline" / "claude-profile"),
        description="Dedicated persistent browser profile holding the Claude.ai login.",
    )
    claude_url: str = Field(default="https://claude.ai")
    claude_headless: bool = Field(
        default=False,
        description="Run the Claude.ai browser headless. Claude.ai may block headless browsers.",
    )
    claude_google_account: str = Field(
        default="",
        description="Optional Google account e-mail to auto-select in the login popup.",
    )
    claude_response_timeout_s: int = Field(default=300)

    # ------------------------------------------------------------------
    # Prices
    # ------------------------------------------------------------------
    prices_active_days: int = Field(
        default=30,
        description="Only refresh prices for tickers mentioned in the last N days.",
    )

    # ------------------------------------------------------------------
    # Backend / CORS
    # ------------------------------------------------------------------
    cors_origins: str = Field(
        default="*",
        description="Comma-separated allowed origins for the public API ('*' = any).",
    )
    cors_origin_regex: str = Field(
        default="",
        description="Also allow origins matching this regex, e.g. every Vercel URL of one project: "
        r"^https://stock-news(-[a-z0-9]+-dsurya11s-projects)?\.vercel\.app$",
    )
    vercel_url: str = Field(default="", description="Deprecated: added to CORS_ORIGINS when set.")
    public_api_url: str = Field(
        default="",
        description="The API as the hosted dashboard reaches it (the Tailscale Funnel URL). Checked by make up / make doctor.",
    )
    public_site_url: str = Field(default="", description="The hosted dashboard (Vercel). Checked by make up / make doctor.")

    # ------------------------------------------------------------------
    # Accounts
    # ------------------------------------------------------------------
    google_client_id: str = Field(
        default="",
        description="Google OAuth client ID for 'Continue with Google'. Empty = email/password only.",
    )
    auth_session_days: int = Field(default=30, description="How long a login lasts.")

    # ------------------------------------------------------------------
    # Operations: alerts and backups (pipeline/ops/)
    # ------------------------------------------------------------------
    alert_after_failures: int = Field(
        default=2,
        description="Alert when the same stage fails this many scheduled runs in a row.",
    )
    alert_desktop: bool = Field(default=True, description="Desktop notifications (notify-send).")
    alert_webhook_url: str = Field(
        default="",
        description="Also POST alerts here as plain text, e.g. https://ntfy.sh/<your-topic> for phone pushes.",
    )
    healthcheck_url: str = Field(
        default="",
        description="Dead-man's switch pinged after every scheduled run (<url> ok, <url>/fail), e.g. healthchecks.io.",
    )
    backup_dir: str = Field(
        default=str(Path.home() / ".local" / "share" / "stock-news-pipeline" / "backups"),
        description="Where database dumps are written.",
    )
    backup_keep: int = Field(default=14, description="Dumps to keep (one a day from the timer).")
    postgres_container: str = Field(default="stocknews-postgres", description="Docker container running Postgres.")

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    log_dir: str = Field(default=str(PROJECT_ROOT / "logs"))
    log_level: str = Field(default="INFO")

    # ------------------------------------------------------------------
    # Readiness gate thresholds
    # ------------------------------------------------------------------
    gate_min_days: int = Field(default=60, description="Days of coverage needed for 100% readiness.")
    gate_max_gap_days: int = Field(default=3)
    gate_min_articles_per_sector_day: int = Field(default=3)
    gate_min_sectors: int = Field(default=5)
    gate_min_extracted_per_sector: int = Field(default=100)

    @field_validator("neon_db_url", "api_db_url", "auth_db_url", "finnhub_api_key", "anthropic_api_key", "google_client_id")
    @classmethod
    def _drop_placeholders(cls, value: str) -> str:
        """Treat untouched .env.example placeholders as 'not configured'."""
        value = (value or "").strip()
        return "" if _is_placeholder(value) else value

    # ------------------------------------------------------------------
    # Derived helpers
    # ------------------------------------------------------------------
    @property
    def fetch_skip_domain_set(self) -> frozenset[str]:
        return frozenset(d.lower() for d in _split_csv(self.fetch_skip_domains))

    @property
    def india_feed_list(self) -> list[str]:
        return _split_csv(self.india_feeds)

    @property
    def report_provider_list(self) -> list[str]:
        return [p.lower() for p in _split_csv(self.report_providers)]

    @property
    def cors_origin_list(self) -> list[str]:
        origins = _split_csv(self.cors_origins)
        if self.vercel_url and not _is_placeholder(self.vercel_url) and "*" not in origins:
            origins.append(self.vercel_url.rstrip("/"))
        return origins or ["*"]


# Module-level singleton — import this everywhere.
settings = Settings()
