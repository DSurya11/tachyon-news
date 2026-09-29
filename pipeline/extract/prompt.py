"""
pipeline/extract/prompt.py
──────────────────────────
Prompts for OmniRoute extraction plus normalisation/validation of the
model's JSON output.

Free-tier models are sloppy about casing, types and enum values, so the
output is *normalised* first (coerced into the canonical shape) and only
rejected when it is unusable.
"""
from __future__ import annotations

import re
from typing import Any

from pipeline.symbols import canonical, is_unlisted

SYSTEM_PROMPT = """\
You are a financial news extraction engine. Read the article and return ONE JSON
object with EXACTLY these 8 keys:

{
  "tickers":    [uppercase exchange ticker symbols the article is about, e.g. "NVDA"; Indian-listed companies use the NSE symbol + ".NS", e.g. "RELIANCE.NS"; cryptocurrencies use "<COIN>-USD", e.g. "BTC-USD"; indices use "SPX", "DJI", "NDX", "NIFTY", "SENSEX"],
  "event_type": one of "earnings" | "merger" | "macro" | "regulatory" | "product" | "personnel" | "legal" | "other",
  "sentiment":  one of "bullish" | "bearish" | "neutral",
  "key_facts":  [up to 5 short factual strings],
  "numbers":    [up to 5 objects {"value": "<number exactly as written in the article>", "unit": "<unit>", "context": "<few words>"}],
  "one_line":   "one neutral sentence summarising the article, max 120 characters",
  "evidence":   "a verbatim quote (max 200 characters) copied exactly from the article body",
  "sector":     the article's main sector, one of "Technology" | "Health Care" | "Financials" | "Energy" | "Industrials" | "Materials" | "Utilities" | "Real Estate" | "Consumer Discretionary" | "Consumer Staples" | "Communication Services" | "Macro" (economy, rates, currencies, broad market)
}

Rules:
- Output the JSON object only: no markdown fences, no commentary, no reasoning.
- "tickers": only real listed symbols you are certain of — omit any you would have to guess (use [] when unsure).
  Indian stocks use the exact NSE trading symbol (HCLTECH.NS, not HCLT.NS; CANBK.NS, not CANBANK.NS).
  Unlisted organisations (exchanges, regulators, private companies) have no ticker.
- "evidence" and every "numbers[].value" must be copied character-for-character from the article text.
- Use [] for empty arrays and "" for empty strings.
"""

HEADLINE_ONLY_NOTE = (
    "(No article body is available — extract from the headline only. "
    'Set "evidence" to "" and "numbers" to [].)'
)


def build_user_prompt(headline: str, body: str | None, max_body_chars: int = 4000) -> str:
    """User message for one article (headline-only when no body is available)."""
    if body and body.strip():
        return f"HEADLINE: {headline}\n\nBODY:\n{body.strip()[:max_body_chars]}"
    return f"HEADLINE: {headline}\n\n{HEADLINE_ONLY_NOTE}"


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = frozenset({"tickers", "event_type", "sentiment", "key_facts", "numbers", "one_line", "evidence"})

VALID_EVENT_TYPES = frozenset({"earnings", "merger", "macro", "regulatory", "product", "personnel", "legal", "other"})

VALID_SENTIMENTS = frozenset({"bullish", "bearish", "neutral"})

# GICS sectors, spelled as the Finviz sector map spells them. "Macro" maps to None
# so the article falls into the dashboard's "Macro & Markets" bucket.
VALID_SECTORS = frozenset({
    "Technology", "Health Care", "Financials", "Energy", "Industrials", "Materials", "Utilities",
    "Real Estate", "Consumer Discretionary", "Consumer Staples", "Communication Services",
})
_SECTOR_ALIASES = {
    "healthcare": "Health Care", "financial": "Financials", "finance": "Financials", "banking": "Financials",
    "information technology": "Technology", "tech": "Technology", "it": "Technology",
    "communication": "Communication Services", "telecom": "Communication Services", "media": "Communication Services",
    "consumer cyclical": "Consumer Discretionary", "consumer defensive": "Consumer Staples",
    "basic materials": "Materials", "industrial": "Industrials", "realty": "Real Estate",
}
_SECTOR_BY_LOWER = {s.lower(): s for s in VALID_SECTORS} | _SECTOR_ALIASES

_SENTIMENT_ALIASES = {"positive": "bullish", "negative": "bearish", "mixed": "neutral"}
_EVENT_ALIASES = {
    "m&a": "merger",
    "acquisition": "merger",
    "earning": "earnings",
    "economic": "macro",
    "economy": "macro",
    "lawsuit": "legal",
    "litigation": "legal",
    "regulation": "regulatory",
    "management": "personnel",
}
# US-style symbols (NVDA, BRK.B), or longer Indian symbols only with an NSE/BSE suffix (RELIANCE.NS).
_TICKER_RE = re.compile(r"^(?:[A-Z][A-Z0-9]{0,5}(?:[.\-][A-Z0-9]{1,3})?|[A-Z][A-Z0-9&\-]{0,14}\.(?:NS|BO))$")


def _as_list(value: Any) -> list:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    return [value]


def _clean_ticker(raw: Any) -> str | None:
    sym = str(raw).strip().upper().lstrip("$")
    sym = canonical(sym.split(":")[-1])  # "NASDAQ:NVDA" → "NVDA"; "BTC" → "BTC-USD"; "NIFTY 50" → "NIFTY"
    return sym if _TICKER_RE.match(sym) and not is_unlisted(sym) else None


def normalize_extraction(data: dict) -> dict:
    """Coerce a raw LLM dict into the canonical extraction shape."""
    tickers: list[str] = []
    for raw in _as_list(data.get("tickers")):
        sym = _clean_ticker(raw)
        if sym and sym not in tickers:
            tickers.append(sym)

    event_type = str(data.get("event_type") or "other").strip().lower()
    event_type = _EVENT_ALIASES.get(event_type, event_type)
    if event_type not in VALID_EVENT_TYPES:
        event_type = "other"

    sentiment = str(data.get("sentiment") or "neutral").strip().lower()
    sentiment = _SENTIMENT_ALIASES.get(sentiment, sentiment)
    if sentiment not in VALID_SENTIMENTS:  # e.g. "slightly bullish"
        sentiment = "bullish" if "bull" in sentiment else "bearish" if "bear" in sentiment else "neutral"

    key_facts = [str(f).strip() for f in _as_list(data.get("key_facts")) if str(f).strip()][:5]

    numbers: list[dict[str, str]] = []
    for n in _as_list(data.get("numbers")):
        if isinstance(n, dict) and str(n.get("value", "")).strip():
            numbers.append(
                {
                    "value": str(n["value"]).strip(),
                    "unit": str(n.get("unit") or "").strip(),
                    "context": str(n.get("context") or "").strip(),
                }
            )
        elif isinstance(n, int | float | str) and str(n).strip():
            numbers.append({"value": str(n).strip(), "unit": "", "context": ""})

    return {
        "tickers": tickers,
        "event_type": event_type,
        "sentiment": sentiment,
        "key_facts": key_facts,
        "numbers": numbers[:5],
        "one_line": str(data.get("one_line") or "").strip()[:300],
        "evidence": str(data.get("evidence") or "").strip(),
        "sector": _SECTOR_BY_LOWER.get(str(data.get("sector") or "").strip().lower()),
    }


def validate_extraction(data: dict) -> list[str]:
    """
    Validate a *normalised* extraction dict.
    Returns a list of error strings (empty = valid).
    """
    errors: list[str] = []
    missing = REQUIRED_FIELDS - set(data)
    if missing:
        errors.append(f"Missing fields: {sorted(missing)}")
    if data.get("sentiment") not in VALID_SENTIMENTS:
        errors.append(f"Invalid sentiment: {data.get('sentiment')!r}")
    if data.get("event_type") not in VALID_EVENT_TYPES:
        errors.append(f"Invalid event_type: {data.get('event_type')!r}")
    if not data.get("one_line"):
        errors.append("one_line is empty")
    for field in ("tickers", "key_facts", "numbers"):
        if not isinstance(data.get(field), list):
            errors.append(f"{field} must be a list")
    return errors
