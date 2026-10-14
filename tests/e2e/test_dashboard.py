"""
Real-browser smoke test of the dashboard: a live API (uvicorn, test database)
plus the built React app (frontend/tachyon-news/dist), driven by headless
Chromium. Skipped when the Playwright browser is not installed or the dashboard
has not been built (`make build-frontend`).
"""
from __future__ import annotations

import functools
import http.server
import socket
import threading
import time
from pathlib import Path

import pytest

from pipeline.db.models import Report, ScrapeRun
from pipeline.market_time import current_trading_day
from tests.factories import NOW, add_article, add_prices

playwright_api = pytest.importorskip("playwright.sync_api")
FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "tachyon-news" / "dist"


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def browser():
    with playwright_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:  # browser binaries missing
            pytest.skip(f"Chromium not installed: {exc}")
        yield b
        b.close()


@pytest.fixture
def servers(engine, clean_db):
    if not (FRONTEND / "index.html").exists():
        pytest.skip("dashboard not built — run `make build-frontend`")
    import uvicorn

    from backend.main import app

    api_port, web_port = _free_port(), _free_port()
    api = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=api_port, log_level="warning"))
    threading.Thread(target=api.run, daemon=True).start()

    web = http.server.ThreadingHTTPServer(("127.0.0.1", web_port), functools.partial(_QuietHandler, directory=str(FRONTEND)))
    threading.Thread(target=web.serve_forever, daemon=True).start()

    deadline = time.time() + 10
    while not api.started and time.time() < deadline:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{web_port}/?api=http://127.0.0.1:{api_port}"
    api.should_exit = True
    web.shutdown()


@pytest.fixture
def seeded(db_session):
    today = current_trading_day()  # the day a brief written now is filed under
    arts = [
        add_article(db_session, id_hint="nv", headline="Nvidia beats estimates", tickers=("NVDA",), sector="Technology"),
        add_article(db_session, id_hint="jp", headline="JPMorgan trading jumps", tickers=("JPM",), sector="Financials",
                    status="extracted"),
        add_article(db_session, id_hint="fd", headline="Fed holds rates", tickers=()),
        add_article(db_session, id_hint="in", headline="Sensex climbs on bank rally", tickers=(), market="india"),
    ]
    add_prices(db_session, "NVDA", [100.0, 104.0, 103.0, 108.0])
    db_session.add(ScrapeRun(started_at=NOW, status="done", items_found=90, error_count=0))
    db_session.add(Report(trading_day=today, provider="omniroute", article_ids=[a.id for a in arts],
                          content=f"## Market Overview\n\nChips led [{arts[0].id}].\n\n## Financials\n\n- Banks rose [{arts[1].id}].",
                          top_picks=[{"id": arts[0].id, "rank": 1, "why": "Sets the tone for AI spending"}]))
    db_session.commit()
    return arts


def test_dashboard_sign_up_browse_and_sign_out(browser, servers, seeded):
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    # Signed out: every route leads to sign-in, remembering where you were going.
    page.goto(servers + "#/wire")
    page.wait_for_url("**#/login?next=%2Fwire")
    page.get_by_role("link", name="Create an account").click()
    page.fill("input[type=email]", "reader@example.com")
    page.fill("input[autocomplete=new-password]", "correct horse")
    page.get_by_role("button", name="Create account").click()

    # Lands on the wire it asked for, with live data from the API.
    page.wait_for_selector("[data-row]")
    assert page.locator("[data-row]").count() == 4

    # Market switch: India only, then back to all markets.
    page.get_by_role("radiogroup", name="Market").get_by_role("radio", name="India").click()
    page.wait_for_function("document.querySelectorAll('[data-row]').length === 1")
    assert "Sensex" in page.inner_text("#wire-rows")
    page.get_by_role("radiogroup", name="Market").get_by_role("radio", name="All").click()
    page.wait_for_function("document.querySelectorAll('[data-row]').length === 4")

    # Top picks: only what the brief's writer ranked, with the reason.
    page.get_by_role("radio", name="Top picks").click()
    page.wait_for_function("document.querySelectorAll('[data-row]').length === 1")
    assert "Sets the tone for AI spending" in page.inner_text("#wire-rows")
    assert "view=top" in page.url

    page.locator("[data-row]").first.click()
    page.wait_for_selector("[role=dialog] >> text=Nvidia beats estimates")
    page.keyboard.press("Escape")

    page.wait_for_selector("[role=dialog]", state="detached")  # shortcuts are ignored while a dialog has focus

    page.keyboard.press("3")
    page.wait_for_selector("#brief-body h2")
    assert "Chips led" in page.inner_text("#brief-body")

    # Sign out from the account menu.
    page.get_by_role("button", name="Account").click()
    page.get_by_role("menuitem", name="Sign out").click()
    page.wait_for_url("**#/login**")

    # Signing back in works; a wrong password shows the API's message.
    page.fill("input[type=email]", "reader@example.com")
    page.fill("input[autocomplete=current-password]", "wrong password")
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_selector("text=Wrong email or password")
    page.fill("input[autocomplete=current-password]", "correct horse")
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_selector("#main h1")

    assert errors == []


def test_dashboard_without_an_api_offers_demo_data(browser, servers):
    page = browser.new_page()
    base = servers.split("?")[0]
    page.goto(base + "?api=http://127.0.0.1:9#/")  # nothing listens on port 9
    page.wait_for_selector("text=Can't reach the server")
    page.goto(base + "?demo=1#/")
    page.wait_for_selector("text=Showing sample data.")
    page.wait_for_selector("#main h1")
