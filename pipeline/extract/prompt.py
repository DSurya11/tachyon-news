"""
pipeline/extract/prompt.py
──────────────────────────
Builds the system and user prompts for OmniRoute extraction.

The LLM must return a strict JSON object with exactly 7 fields.
We embed a JSON schema in the system prompt and add explicit
formatting guards to minimise hallucination.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# System prompt — pinned, never changes per-article
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a financial news extraction engine. Your task is to read a news article
and return a single JSON object with EXACTLY these 7 keys — no more, no less:

{
  "tickers":    <array of uppercase stock ticker symbols mentioned, e.g. ["NVDA", "AMD"]>,
  "event_type": <one of: "earnings"|"merger"|"macro"|"regulatory"|"product"|"personnel"|"legal"|"other">,
  "sentiment":  <one of: "bullish"|"bearish"|"neutral">,
  "key_facts":  <array of short fact strings, max 5 items>,
  "numbers":    <array of {\"value\": \"<numeric string>\", \"unit\": \"<unit>\", \"context\": \"<brief context>\"}, max 5 items>,
  "one_line":   <one public-safe sentence summarising the article, max 120 chars>,
  "evidence":   <a verbatim quote from the article body that best supports your sentiment, max 200 chars>
}

STRICT RULES:
1. Return ONLY the JSON object. No markdown fences, no preamble, no explanation.
2. "tickers" must only contain real exchange-traded symbols; leave empty [] if unsure.
3. "evidence" MUST be copied verbatim from the article — do not paraphrase.
4. "numbers.value" must be a plain numeric string as it appears in the article (e.g. "30.0", "12").
5. If a field has no data, use [] for arrays and "other"/"neutral"/"" for strings.
6. Respond with valid JSON only.
(Note: Cache busted after 512-token truncation bug)
"""

# ---------------------------------------------------------------------------
# User prompt builder
# ---------------------------------------------------------------------------

def build_user_prompt(headline: str, body: str | None) -> str:
    """
    Construct the user message for a single article.
    Falls back to headline-only when body is unavailable.
    """
    if body and body.strip():
        # Truncate body to 2000 chars to stay within context limits of free models
        body_section = body.strip()[:2000]
        content = f"HEADLINE: {headline}\n\nBODY:\n{body_section}"
    else:
        content = (
            f"HEADLINE: {headline}\n\n"
            "(No article body available — extract from headline only. "
            "Set evidence to an empty string.)"
        )
    return content


# ---------------------------------------------------------------------------
# Required output fields for validation
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = {
    "tickers", "event_type", "sentiment",
    "key_facts", "numbers", "one_line", "evidence",
}

VALID_EVENT_TYPES = {
    "earnings", "merger", "macro", "regulatory",
    "product", "personnel", "legal", "other",
}

VALID_SENTIMENTS = {"bullish", "bearish", "neutral"}


def validate_extraction(data: dict) -> list[str]:
    """
    Validate a parsed extraction dict.
    Returns a list of error strings (empty = valid).
    """
    errors: list[str] = []

    missing = REQUIRED_FIELDS - set(data.keys())
    if missing:
        errors.append(f"Missing fields: {missing}")

    if "event_type" in data and data["event_type"] not in VALID_EVENT_TYPES:
        errors.append(f"Invalid event_type: {data['event_type']!r}")

    if "sentiment" in data and data["sentiment"] not in VALID_SENTIMENTS:
        errors.append(f"Invalid sentiment: {data['sentiment']!r}")

    if "tickers" in data and not isinstance(data["tickers"], list):
        errors.append("tickers must be a list")

    if "key_facts" in data and not isinstance(data["key_facts"], list):
        errors.append("key_facts must be a list")

    if "numbers" in data:
        if not isinstance(data["numbers"], list):
            errors.append("numbers must be a list")
        else:
            for i, n in enumerate(data["numbers"]):
                if not isinstance(n, dict) or "value" not in n:
                    errors.append(f"numbers[{i}] missing 'value' key")

    return errors
