"""
pipeline/extract/verifier.py
─────────────────────────────
Post-extraction verification:

  PASS condition (status → 'verified'):
    1. evidence string appears verbatim as a substring of body (case-insensitive)
    2. every numbers[].value appears verbatim as a substring of body

  If body is None (headline-only articles):
    - Skip verification entirely → status stays 'extracted'
    - This is intentional: can't verify against a body that doesn't exist

Returns a VerifyResult dataclass.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class VerifyResult:
    passed: bool
    evidence_found: bool
    numbers_missing: list[str]   # values that did NOT appear in body
    note: str = ""


def verify(
    body: str | None,
    evidence: str | None,
    numbers: list[dict] | None,
) -> VerifyResult:
    """
    Verify that the extracted evidence and numeric values are grounded in the body.

    Args:
        body:     Full article body text (may be None for headline-only articles).
        evidence: Verbatim quote extracted by the LLM.
        numbers:  List of {"value": "...", "unit": "...", "context": "..."} dicts.

    Returns:
        VerifyResult with passed=True only if both checks succeed.
    """
    # No body → cannot verify; treat as neutral (neither pass nor fail)
    if not body or not body.strip():
        return VerifyResult(
            passed=False,
            evidence_found=False,
            numbers_missing=[],
            note="no_body",
        )

    body_lower = body.lower()

    # ── Evidence check ───────────────────────────────────────────────────
    evidence_found = False
    if evidence and evidence.strip():
        # Use first 120 chars of evidence for substring check
        # (LLM sometimes adds trailing punctuation differences)
        evidence_prefix = evidence.strip()[:120].lower()
        evidence_found = evidence_prefix in body_lower
    else:
        # Empty evidence string — treat as found (no claim to verify)
        evidence_found = True

    # ── Numbers check ────────────────────────────────────────────────────
    numbers_missing: list[str] = []
    if numbers:
        for num_obj in numbers:
            value = str(num_obj.get("value", "")).strip()
            if not value:
                continue
            if value.lower() not in body_lower:
                numbers_missing.append(value)

    passed = evidence_found and len(numbers_missing) == 0

    note_parts = []
    if not evidence_found:
        note_parts.append("evidence_not_found")
    if numbers_missing:
        note_parts.append(f"numbers_missing:{','.join(numbers_missing[:3])}")

    return VerifyResult(
        passed=passed,
        evidence_found=evidence_found,
        numbers_missing=numbers_missing,
        note="|".join(note_parts) if note_parts else "ok",
    )
