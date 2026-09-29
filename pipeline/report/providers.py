"""
pipeline/report/providers.py
────────────────────────────
Report writers.  Each provider takes a ReportPrompt and returns Markdown, or
raises ProviderUnavailable (not configured / cannot run here) or another
exception (tried and failed).  The service walks REPORT_PROVIDERS in order.

  anthropic   — Claude via the official Anthropic API (needs ANTHROPIC_API_KEY)
  claude_web  — Claude.ai in a real browser via Playwright (needs a logged-in
                profile and a display unless CLAUDE_HEADLESS=true)
  omniroute   — the local OmniRoute router (free models); the fallback that
                keeps a report on the dashboard when the others are down
"""
from __future__ import annotations

import logging
import os
import re
import sys
from collections.abc import Callable

from pipeline.config import settings
from pipeline.report.prompt_builder import ReportPrompt

log = logging.getLogger(__name__)

MIN_REPORT_CHARS = 200
_FALLBACK_MODELS = {"claude-opus-5", "claude-fable-5-1"}
_THINK_RE = re.compile(r"<think(?:ing)?>.*?</think(?:ing)?>", re.DOTALL | re.IGNORECASE)
_FENCE_RE = re.compile(r"^```(?:markdown|md)?\s*\n(.*)\n```\s*$", re.DOTALL)


class ProviderUnavailable(RuntimeError):
    """The provider is not configured or cannot run in this environment."""


def clean_report(text: str) -> str:
    """Strip reasoning blocks and a wrapping code fence some models add."""
    text = _THINK_RE.sub("", text or "").strip()
    m = _FENCE_RE.match(text)
    return (m.group(1) if m else text).strip()


def _check(text: str, provider: str) -> str:
    text = clean_report(text)
    if len(text) < MIN_REPORT_CHARS:
        raise RuntimeError(f"{provider} returned a suspiciously short report ({len(text)} chars)")
    return text


# ---------------------------------------------------------------------------
# Anthropic API
# ---------------------------------------------------------------------------

def generate_with_anthropic(prompt: ReportPrompt) -> str:
    if not settings.anthropic_api_key:
        raise ProviderUnavailable("ANTHROPIC_API_KEY is not set")
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    request: dict = {
        "model": settings.anthropic_model,
        "max_tokens": 64000,
        "system": prompt.system,
        "messages": [{"role": "user", "content": prompt.user}],
    }
    if settings.anthropic_model in _FALLBACK_MODELS:
        # Server-side refusal fallback: a declined request is re-run on
        # Anthropic's recommended fallback model inside the same call.
        request |= {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}

    with client.beta.messages.stream(**request) as stream:
        message = stream.get_final_message()

    if message.stop_reason == "refusal":
        raise RuntimeError(f"Claude declined the request: {message.stop_details}")
    if message.stop_reason == "max_tokens":
        log.warning("Anthropic report hit max_tokens; keeping the partial report.")
    text = "".join(block.text for block in message.content if block.type == "text")
    log.info(
        "Anthropic report: model=%s in=%d out=%d tokens",
        message.model, message.usage.input_tokens, message.usage.output_tokens,
    )
    return _check(text, "anthropic")


# ---------------------------------------------------------------------------
# OmniRoute
# ---------------------------------------------------------------------------

def generate_with_omniroute(prompt: ReportPrompt) -> str:
    from openai import APIConnectionError, OpenAI

    client = OpenAI(
        base_url=settings.omniroute_api_url,
        api_key=settings.omniroute_api_key or "unused",
        timeout=max(settings.omniroute_timeout_s, 180.0),
        max_retries=1,
    )
    try:
        resp = client.chat.completions.create(
            model=settings.omniroute_report_model or settings.omniroute_model,
            messages=[
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user},
            ],
            temperature=0.3,
            max_tokens=8000,
        )
    except APIConnectionError as exc:
        raise ProviderUnavailable(f"OmniRoute unreachable at {settings.omniroute_api_url}") from exc
    if not resp.choices:
        raise RuntimeError("OmniRoute returned no choices")
    return _check(resp.choices[0].message.content or "", "omniroute")


# ---------------------------------------------------------------------------
# Claude.ai browser automation
# ---------------------------------------------------------------------------

def generate_with_claude_web(prompt: ReportPrompt) -> str:
    if not settings.claude_headless and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        raise ProviderUnavailable("no display for the headed browser (set CLAUDE_HEADLESS=true or run with DISPLAY)")
    from pipeline.report.claude_web import login_required, run_claude_web

    if login_required() and not sys.stdin.isatty():
        raise ProviderUnavailable("Claude.ai session expired — run `make claude-login`")
    return _check(run_claude_web(prompt.combined), "claude_web")


PROVIDERS: dict[str, Callable[[ReportPrompt], str]] = {
    "anthropic": generate_with_anthropic,
    "claude_web": generate_with_claude_web,
    "omniroute": generate_with_omniroute,
}
