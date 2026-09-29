"""
pipeline/extract/verifier.py
─────────────────────────────
Post-extraction grounding check.

  PASS (status → 'verified') when
    1. the evidence quote appears in the body, and
    2. every numbers[].value appears in the body.

Both sides are normalised first (case, quote marks, dashes, whitespace,
thousands separators) so a faithful quote is not rejected over typography.
An evidence quote the model elided with "..." passes when each substantial
fragment is found, and a near-verbatim quote (models silently fix source
typos) passes when it anchors on an exact 20-char chunk and is ≥92% similar.

Headline-only articles (no body) cannot be verified and stay 'extracted'.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

EVIDENCE_PREFIX_CHARS = 120
MIN_FRAGMENT_CHARS = 20
FUZZY_ANCHOR_CHARS = 20
FUZZY_MIN_RATIO = 0.92

_TRANSLATE = str.maketrans(
    {
        "‘": "'", "’": "'", "‚": "'", "′": "'",
        "“": '"', "”": '"', "„": '"', "″": '"',
        "–": "-", "—": "-", "−": "-",
        " ": " ", " ": " ", " ": " ",
    }
)
_WS_RE = re.compile(r"\s+")
_THOUSANDS_RE = re.compile(r"(?<=\d),(?=\d{3}\b)")
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
_ELLIPSIS_RE = re.compile(r"\.\.\.|…")
_QUOTES_RE = re.compile(r"[\"'`]")


def normalize_text(text: str) -> str:
    text = text.translate(_TRANSLATE).lower()
    text = _THOUSANDS_RE.sub("", text)
    return _WS_RE.sub(" ", text).strip()


@dataclass
class VerifyResult:
    passed: bool
    evidence_found: bool
    numbers_missing: list[str]  # values that did NOT appear in body
    note: str = ""


def _fuzzy_in(probe: str, body: str) -> bool:
    """Near-verbatim match: anchor on an exact chunk, then compare the aligned window."""
    n = len(probe)
    if n < FUZZY_ANCHOR_CHARS * 2:
        return False
    for start in range(0, n - FUZZY_ANCHOR_CHARS + 1, FUZZY_ANCHOR_CHARS // 2):
        idx = body.find(probe[start : start + FUZZY_ANCHOR_CHARS])
        if idx == -1:
            continue
        begin = max(0, idx - start)
        window = body[begin : begin + n + 5]
        if SequenceMatcher(None, probe, window, autojunk=False).ratio() >= FUZZY_MIN_RATIO:
            return True
    return False


def _evidence_in_body(evidence: str, body_norm: str) -> bool:
    # Quote marks are dropped entirely: models routinely swap " for ' inside quotes.
    body_cmp = _QUOTES_RE.sub("", body_norm)
    ev = _QUOTES_RE.sub("", normalize_text(evidence)).strip()
    fragments = [f.strip(" ,;:") for f in _ELLIPSIS_RE.split(ev)]
    fragments = [f for f in fragments if len(f) >= MIN_FRAGMENT_CHARS] or [ev]
    for frag in fragments:
        probe = frag[:EVIDENCE_PREFIX_CHARS].rstrip(" .")
        if probe and probe not in body_cmp and not _fuzzy_in(probe, body_cmp):
            return False
    return True


def _contains_token(needle: str, haystack: str) -> bool:
    """Substring match that won't let "46" match inside "46.5" or "146"."""
    return re.search(rf"(?<![\d.]){re.escape(needle)}(?!\d|\.\d)", haystack) is not None


def _number_in_body(value: str, body_norm: str) -> bool:
    norm = normalize_text(value)
    if _contains_token(norm, body_norm):
        return True
    # "$1.5 billion" vs "1.5 billion"; "30%" vs "30 percent" — require the digits
    digits = _NUMBER_RE.findall(norm)
    return bool(digits) and all(_contains_token(d, body_norm) for d in digits)


def verify(body: str | None, evidence: str | None, numbers: list[dict] | None) -> VerifyResult:
    """Check that the extracted evidence and numeric values are grounded in the body."""
    if not body or not body.strip():
        return VerifyResult(passed=False, evidence_found=False, numbers_missing=[], note="no_body")

    body_norm = normalize_text(body)

    # Empty evidence makes no claim, so there is nothing to disprove.
    evidence_found = _evidence_in_body(evidence, body_norm) if evidence and evidence.strip() else True

    numbers_missing = [
        value
        for value in (str(n.get("value", "")).strip() for n in (numbers or []) if isinstance(n, dict))
        if value and not _number_in_body(value, body_norm)
    ]

    note_parts = []
    if not evidence_found:
        note_parts.append("evidence_not_found")
    if numbers_missing:
        note_parts.append(f"numbers_missing:{','.join(numbers_missing[:3])}")

    return VerifyResult(
        passed=evidence_found and not numbers_missing,
        evidence_found=evidence_found,
        numbers_missing=numbers_missing,
        note="|".join(note_parts) or "ok",
    )
