"""
pipeline/report/top_picks.py
────────────────────────────
The report writer ends its reply with a machine-readable ranking of the day's
must-read stories (the dashboard's "Top picks"):

    ```json
    {"top_picks": [{"id": 1042, "why": "Guidance raise resets AI capex expectations"}]}
    ```

`split_top_picks` removes that block from the published Markdown and returns the
validated picks. Chat UIs sometimes drop the code fence when text is copied, so a
bare `{"top_picks": ...}` object is accepted too. A report without the block is
still a valid report — it just has no picks.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterable

MAX_WHY_CHARS = 160

_FENCED_RE = re.compile(r"```(?:json)?\s*(\{.*?\"top_picks\".*?\})\s*```", re.DOTALL | re.IGNORECASE)
# Label lines some writers put above the block ("Top picks:", "json", "Copy").
_TRAILING_LABEL_RE = re.compile(r"(?:\n\s*(?:#+\s*)?(?:top picks:?|json|copy)\s*)+$", re.IGNORECASE)


def _decode_bare(text: str) -> tuple[dict | None, int]:
    """Find a bare {"top_picks": ...} object; returns (object, start index)."""
    key = text.rfind('"top_picks"')
    if key == -1:
        return None, -1
    start = text.rfind("{", 0, key)
    if start == -1:
        return None, -1
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError:
        return None, -1
    return (obj if isinstance(obj, dict) else None), start


def _validate(raw: object, valid_ids: set[int], limit: int) -> list[dict]:
    picks: list[dict] = []
    seen: set[int] = set()
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        try:
            article_id = int(item.get("id"))
        except (TypeError, ValueError):
            continue
        if article_id not in valid_ids or article_id in seen:
            continue
        seen.add(article_id)
        why = " ".join(str(item.get("why") or "").split())[:MAX_WHY_CHARS]
        picks.append({"id": article_id, "rank": len(picks) + 1, "why": why})
        if len(picks) >= limit:
            break
    return picks


def split_top_picks(content: str, valid_ids: Iterable[int], limit: int) -> tuple[str, list[dict]]:
    """Return (report Markdown without the picks block, validated picks)."""
    valid = set(valid_ids)
    fenced = list(_FENCED_RE.finditer(content))
    m = fenced[-1] if fenced else None  # the last fenced block wins
    if m is not None:
        try:
            obj = json.loads(m.group(1))
        except json.JSONDecodeError:
            obj = None
        body = content[: m.start()] + content[m.end() :]
    else:
        obj, start = _decode_bare(content)
        body = content[:start] if obj is not None else content

    if obj is None:
        return content.strip(), []
    body = _TRAILING_LABEL_RE.sub("", body.rstrip()).rstrip()
    return body, _validate(obj.get("top_picks"), valid, limit)
