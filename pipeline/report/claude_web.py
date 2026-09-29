"""
pipeline/report/claude_web.py
─────────────────────────────
Drives Claude.ai in a persistent Playwright browser profile.

One-time setup (opens a window; log in, then it closes by itself):
    make claude-login

The profile lives in CHROME_PROFILE_DIR and must be dedicated to this tool:
pointing it at your everyday Chrome profile fails whenever Chrome is open
("profile already in use") and Chromium cannot decrypt Chrome's cookies.

Run it headed (CLAUDE_HEADLESS=false, the default): Claude.ai sits behind
Cloudflare, whose bot check ("Just a moment...") never clears for a headless
browser even with a valid login.

This is best-effort UI automation — Claude.ai's DOM can change without
notice.  The report service falls back to other providers when it fails.

Unattended runs (no terminal: the scheduled job) never wait for a manual login.
When the session has expired, the first such run records it
(LOG_DIR/.claude_login_required) and later runs skip this provider straight
away, instead of opening a browser window every hour, until `make claude-login`
succeeds.
"""
from __future__ import annotations

import logging
import sys
import time
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import BrowserContext, Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from pipeline.config import settings

log = logging.getLogger(__name__)

EDITOR_SELECTOR = 'div[contenteditable="true"]'
RESPONSE_SELECTOR = "div.standard-markdown"
SEND_BUTTON_SELECTOR = 'button[aria-label="Send message"], button[aria-label="Send Message"]'
POLL_INTERVAL_MS = 2000
STABLE_POLLS_REQUIRED = 3
LOGIN_TIMEOUT_MS = 5 * 60 * 1000


class ClaudeWebError(RuntimeError):
    pass


def _login_marker() -> Path:
    return Path(settings.log_dir) / ".claude_login_required"


def login_required() -> bool:
    """True after an unattended run found the Claude.ai session logged out."""
    return _login_marker().exists()


def _set_login_required(required: bool) -> None:
    marker = _login_marker()
    if required:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
    else:
        marker.unlink(missing_ok=True)


def _interactive() -> bool:
    """Someone is at a terminal who could log in (not the scheduled job)."""
    return not settings.claude_headless and sys.stdin.isatty()


@contextmanager
def _browser(headless: bool):
    profile = Path(settings.chrome_profile_dir).expanduser()
    profile.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        try:
            context: BrowserContext = pw.chromium.launch_persistent_context(
                user_data_dir=str(profile),
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"],
                viewport={"width": 1280, "height": 900},
            )
        except Exception as exc:
            if "already in use" in str(exc) or "ProcessSingleton" in str(exc):
                raise ClaudeWebError(f"browser profile {profile} is in use by another browser") from exc
            raise
        try:
            yield context
        finally:
            context.close()


def _new_chat_page(context: BrowserContext) -> Page:
    page = context.pages[0] if context.pages else context.new_page()
    page.goto(f"{settings.claude_url.rstrip('/')}/new", timeout=60_000, wait_until="domcontentloaded")
    return page


def _try_google_login(context: BrowserContext, page: Page) -> None:
    """Best-effort 'Continue with Google' using CLAUDE_GOOGLE_ACCOUNT."""
    button = page.get_by_text("Continue with Google")
    if not settings.claude_google_account or not button.is_visible(timeout=5000):
        return
    try:
        with context.expect_page(timeout=10_000) as popup_info:
            button.click()
        popup = popup_info.value
        account = popup.locator(f'div[data-identifier="{settings.claude_google_account}"]')
        account.wait_for(timeout=10_000)
        account.click()
        cont = popup.locator('span:has-text("Continue")')
        try:
            cont.first.wait_for(state="visible", timeout=5000)
            cont.first.click()
        except PlaywrightTimeoutError:
            pass
        log.info("Selected Google account %s", settings.claude_google_account)
    except Exception as exc:  # noqa: BLE001 — purely best-effort
        log.warning("Automatic Google login failed: %s", exc)


def _wait_for_editor(context: BrowserContext, page: Page, interactive: bool) -> None:
    try:
        page.wait_for_selector(EDITOR_SELECTOR, timeout=15_000)
        return
    except PlaywrightTimeoutError:
        pass
    _try_google_login(context, page)
    timeout = LOGIN_TIMEOUT_MS if interactive else 60_000
    try:
        page.wait_for_selector(EDITOR_SELECTOR, timeout=timeout)
    except PlaywrightTimeoutError as exc:
        if _is_bot_check(page):
            hint = " — headless browsers are blocked; set CLAUDE_HEADLESS=false" if settings.claude_headless else ""
            raise ClaudeWebError(f"Claude.ai's Cloudflare bot check did not clear{hint}") from exc
        _set_login_required(True)
        raise ClaudeWebError("not logged in to Claude.ai — run `make claude-login` once") from exc


def _is_bot_check(page: Page) -> bool:
    """Cloudflare's interstitial ("Just a moment...") rather than Claude.ai itself."""
    try:
        return "just a moment" in page.title().lower() or page.locator("#challenge-running, #cf-challenge-running").count() > 0
    except Exception:  # noqa: BLE001 — page navigating
        return False


def _read_last_response(page: Page) -> str:
    try:
        messages = page.locator(RESPONSE_SELECTOR)
        return messages.last.inner_text() if messages.count() else ""
    except Exception:  # noqa: BLE001 — navigation from /new to /chat/<id> mid-read
        return ""


def _last_response_markdown(page: Page, fallback: str) -> str:
    try:
        import markdownify

        html = page.locator(RESPONSE_SELECTOR).last.inner_html()
        return markdownify.markdownify(html, heading_style="ATX").strip() or fallback
    except Exception as exc:  # noqa: BLE001
        log.warning("HTML → Markdown conversion failed (%s); using plain text", exc)
        return fallback


def run_claude_web(prompt: str) -> str:
    """Send `prompt` in a new Claude.ai chat and return the reply as Markdown."""
    log.info("Claude.ai automation: prompt %d chars", len(prompt))
    with _browser(headless=settings.claude_headless) as context:
        page = _new_chat_page(context)
        _wait_for_editor(context, page, interactive=_interactive())
        _set_login_required(False)

        editor = page.locator(EDITOR_SELECTOR).first
        editor.fill(prompt)
        page.wait_for_timeout(1000)
        send = page.locator(SEND_BUTTON_SELECTOR)
        if send.count():
            send.first.click()
        else:
            editor.press("Control+Enter")

        deadline = time.monotonic() + settings.claude_response_timeout_s
        last_text, stable = "", 0
        while time.monotonic() < deadline:
            page.wait_for_timeout(POLL_INTERVAL_MS)
            current = _read_last_response(page)
            if not current:
                continue
            if current == last_text:
                stable += 1
                if stable >= STABLE_POLLS_REQUIRED:
                    log.info("Claude.ai response complete: %d chars", len(current))
                    return _last_response_markdown(page, current)
            else:
                stable, last_text = 0, current

        raise ClaudeWebError(
            f"no complete response within {settings.claude_response_timeout_s}s "
            f"(got {len(last_text)} chars)"
        )


def login() -> int:
    """Open a headed browser so the user can log in to Claude.ai once."""
    print(f"Opening Claude.ai with profile {settings.chrome_profile_dir}")
    print("Log in in the browser window; it closes automatically once the chat box appears (5 min max).")
    with _browser(headless=False) as context:
        page = _new_chat_page(context)
        try:
            _wait_for_editor(context, page, interactive=True)
        except ClaudeWebError as exc:
            print(f"✗ {exc}", file=sys.stderr)
            return 1
    _set_login_required(False)
    print("✓ Logged in. The pipeline can now use the claude_web report provider.")
    if settings.claude_headless:
        print("⚠ CLAUDE_HEADLESS=true: Claude.ai's bot check blocks headless browsers, so the pipeline will fail "
              "even though you are logged in. Set CLAUDE_HEADLESS=false in .env.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) > 1 and sys.argv[1] == "login":
        sys.exit(login())
    print(run_claude_web("Reply with exactly: TEST SUCCESSFUL"))
