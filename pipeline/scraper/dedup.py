"""
pipeline/scraper/dedup.py
─────────────────────────
Deduplication utilities for article URLs and headlines.

Rules (from implementation plan):
  - canonical_url: lowercase, drop fragment, strip trailing slash,
                   strip utm_*, mod, fbclid query params
  - title_hash:    sha256(source_name + normalize_whitespace(headline.lower()))
                   — index only, not UNIQUE; catches same story/same outlet/URL variant
"""
from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# Query params that carry no semantic meaning and vary across reshares
_STRIP_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
    "utm_id", "utm_referrer",
    "fbclid", "gclid", "msclkid", "twclid",
    "mod",           # WSJ "mod=" tracking param
    "ref",           # Bloomberg ref
    "src",           # Reuters src
    "smid", "smtyp", # social media tracking
    "via",
    "ncid",          # CNBC
    "_r",            # NYT
})

_WS_RE = re.compile(r"\s+")


def canonical_url(url: str) -> str:
    """
    Normalise a URL into a canonical form used as the UNIQUE key in `articles`.

    Steps:
      1. Lowercase entire URL
      2. Drop fragment (#...)
      3. Strip known tracking query params
      4. Remove trailing slash from path (but not bare domain root)
      5. Reconstruct URL

    Examples:
      "https://Reuters.com/article/foo?utm_source=tw#top" → "https://reuters.com/article/foo"
      "https://finviz.com/news/story?mod=1&id=2"          → "https://finviz.com/news/story?id=2"
    """
    url = url.strip()
    # Step 1: lowercase
    url = url.lower()
    # Step 2: parse (this also drops fragment because we ignore it)
    parsed = urlparse(url)

    # Step 3: strip tracking params
    qs = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
          if k not in _STRIP_PARAMS]
    clean_query = urlencode(qs)

    # Step 4: strip trailing slash from path (but keep bare "/" for domains)
    path = parsed.path.rstrip("/") or "/"

    # Reconstruct without fragment
    canonical = urlunparse((
        parsed.scheme,
        parsed.netloc,
        path,
        parsed.params,
        clean_query,
        "",           # no fragment
    ))
    return canonical


def title_hash(source_name: str, headline: str) -> str:
    """
    Compute sha256(source_name + normalize_whitespace(headline.lower())).

    This is stored as an index (not UNIQUE) to surface same-story/same-outlet
    duplicates that arrived via different URLs.
    """
    normalised = _WS_RE.sub(" ", headline.lower()).strip()
    raw = (source_name or "") + normalised
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
