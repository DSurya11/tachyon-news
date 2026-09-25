"""
pipeline/noise/tagger.py
────────────────────────
Detects noise articles via regex patterns and tags them.

Five noise types (tagged, never deleted):
  1. law_firm_loss          — law-firm investor-loss solicitations
  2. nasdaq_grant           — Nasdaq inducement-grant notices
  3. dividend_routine       — routine dividend declarations (no surprise)
  4. nasdaq_compliance      — Nasdaq compliance notices
  5. stock_blurb            — auto-generated "stock outperforms market" blurbs

Tags are additive — an article can have multiple tags.
Returns a list of tag strings (empty = not noise).
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Pattern definitions
# Each entry: (tag_name, list_of_compiled_patterns)
# An article is tagged if ANY pattern in a group matches headline or body.
# ---------------------------------------------------------------------------

_PATTERNS: list[tuple[str, list[re.Pattern]]] = [
    (
        "law_firm_loss",
        [
            re.compile(
                r"\b(investors? who (suffered|lost|experienced)|"
                r"securities (class action|fraud) (lawsuit|complaint|investigation)|"
                r"file[sd]? a lawsuit on behalf of|"
                r"loss[- ]recovery|investor alert|shareholder alert|"
                r"NOTICE TO INVESTORS|"
                r"(Robbins|Pomerantz|Rosen|Kessler|Bernstein Liebhard|"
                r"Glancy|Faruqi|Wolf Haldenstein|Block &amp; Leviton|"
                r"Schall|Lifshitz|Levi &amp; Korsinsky|"
                r"Bronstein Gewirtz|Scott\+Scott)\s+&?\s*(LLP|Law))\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(class action|securities fraud|investor (loss|lawsuit|suit))\b",
                re.IGNORECASE,
            ),
        ],
    ),
    (
        "nasdaq_grant",
        [
            re.compile(
                r"\b(inducement grant|nasdaq (listing rule|inducement)|"
                r"granted? (options?|RSUs?|restricted stock units?) as (an? )?inducement|"
                r"new (employee|hire) inducement)\b",
                re.IGNORECASE,
            ),
        ],
    ),
    (
        "dividend_routine",
        [
            re.compile(
                r"\b(declares?|announces?|pays?)\s+(quarterly|monthly|annual|regular|"
                r"semi-annual|special)\s+(cash\s+)?(dividend|distribution)\b",
                re.IGNORECASE,
            ),
            # Catches "Board declares regular quarterly dividend of $X.XX per share"
            re.compile(
                r"\b(quarterly|regular|monthly)\s+(cash\s+)?dividend\b",
                re.IGNORECASE,
            ),
        ],
    ),
    (
        "nasdaq_compliance",
        [
            re.compile(
                r"\b(receives?|received|get|got|issued?)\s+.{0,40}"
                r"(nasdaq|nyse)\s+(deficiency|compliance|notice|letter|"
                r"listing (rule|requirement))\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(nasdaq|nyse)\s+(compliance|listing)\s+"
                r"(notice|letter|requirement|rule)\b",
                re.IGNORECASE,
            ),
        ],
    ),
    (
        "stock_blurb",
        [
            re.compile(
                r"\b(outperform(s|ed|ing)?|underperform(s|ed|ing)?)\s+.{0,20}"
                r"(the\s+)?(market|s&p|nasdaq|dow)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(stock (rises?|gains?|climbs?|falls?|drops?|slides?|tumbles?|surges?|"
                r"soars?|plunges?))\s+(above|below|past|through)?\s*"
                r"(its\s+)?(50|100|200)[- ]day\s+(moving average|MA)\b",
                re.IGNORECASE,
            ),
            # "COMPANY stock up X% this week, here's why" — generic blurb pattern
            re.compile(
                r"\bstock (up|down)\s+\d+(\.\d+)?%\s+(this week|today|"
                r"on the week|year.to.date)\b",
                re.IGNORECASE,
            ),
        ],
    ),
]


def tag_article(headline: str, body: str | None = None) -> list[str]:
    """
    Return a list of noise tag strings for the given article.
    Empty list = not noise.

    Args:
        headline:  Article headline text.
        body:      Optional article body text (checked if headline alone
                   doesn't trigger, to reduce false positives).
    """
    text = headline.lower()
    if body:
        # Check headline first; extend to body only for patterns that need it
        full_text = (headline + " " + body).lower()
    else:
        full_text = text

    tags: list[str] = []
    for tag_name, patterns in _PATTERNS:
        for pattern in patterns:
            # Check headline first (fast path), then full text
            if pattern.search(headline) or (body and pattern.search(full_text)):
                tags.append(tag_name)
                break  # one match per group is enough

    return tags
