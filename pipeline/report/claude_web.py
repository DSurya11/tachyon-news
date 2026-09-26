import logging
import re
import time
from datetime import date
from typing import Optional

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from pipeline.config import settings
from pipeline.db.local import LocalSession
from pipeline.db.models import Report

logger = logging.getLogger(__name__)


def generate_report(trading_day: date, prompt: str, article_ids: list[int]) -> Optional[str]:
    """
    Automates claude.ai using Playwright with a persistent Chrome profile.
    Puts the prompt in a new chat, waits for the generation to stabilize,
    and returns the resulting text.
    On success, stores the report in the `reports` table.
    On failure, logs a warning and returns None.
    """
    logger.info(f"Starting Claude web automation for {trading_day} (prompt len: {len(prompt)})")

    result_text = None
    
    try:
        with sync_playwright() as p:
            # We use launch_persistent_context to share cookies with the user's logged-in Chrome
            context = p.chromium.launch_persistent_context(
                user_data_dir=settings.chrome_profile_dir,
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox"
                ]
            )
            
            page = context.new_page()
            
            # 1. Navigate to Claude
            logger.info("Navigating to https://claude.ai/new")
            page.goto("https://claude.ai/new", timeout=60000, wait_until="domcontentloaded")
            
            # 2. Check for login / text area
            # The chat input area is usually a Prosemirror contenteditable or a generic input
            # Let's wait for either the input field or the Google login button.
            try:
                # Wait up to 10s for the editor to appear
                page.wait_for_selector('div[contenteditable="true"]', timeout=10000)
                logger.info("Found chat input field.")
            except PlaywrightTimeoutError:
                logger.info("Chat input not found immediately. Checking for 'Continue with Google'...")
                # Attempt to click Continue with Google if present
                google_btn = page.get_by_text("Continue with Google")
                if google_btn.is_visible(timeout=5000):
                    logger.info("Clicking 'Continue with Google'. If a popup appears or you need to select an account, PLEASE DO SO MANUALLY IN THE BROWSER NOW. Waiting up to 2 minutes...")
                    google_btn.click()
                    # Wait for redirect and reload
                    page.wait_for_selector('div[contenteditable="true"]', timeout=120000)
                else:
                    logger.warning("Could not find chat input or Google login button. Giving up.")
                    context.close()
                    return None

            # 3. Paste the prompt
            logger.info("Typing prompt...")
            editor = page.locator('div[contenteditable="true"]').first
            editor.fill(prompt)
            
            # Wait a beat for the submit button to become active
            page.wait_for_timeout(1000)
            
            # 4. Submit
            logger.info("Submitting prompt...")
            # The submit button is typically the only button inside the input container or we can just press Enter if we haven't typed newlines.
            # But since prompt has newlines, we should click the Send button.
            # Usually it has an aria-label="Send Message" or is a `<button>` next to the input.
            send_button = page.locator('button[aria-label="Send Message"]')
            if send_button.count() > 0:
                send_button.first.click()
            else:
                # Fallback: find the SVG icon for send or just the last button in the chat bar
                editor.press("Meta+Enter")  # Mac shortcut to send multiline
                editor.press("Control+Enter") # Windows/Linux shortcut
            
            # 5. Poll for response stabilization
            logger.info("Waiting for response to stabilize...")
            
            # The responses are typically in a container. Claude's responses are inside `div.font-claude-message` or similar.
            # We'll just grab the text of the LAST message block in the DOM.
            start_time = time.time()
            max_wait = 300  # 5 minutes max
            stable_count = 0
            last_text = ""
            
            while True:
                if time.time() - start_time > max_wait:
                    logger.warning("Timed out waiting for Claude response (5 mins).")
                    break
                    
                page.wait_for_timeout(2000)
                
                # We need to find the AI's response blocks. Usually they are the only divs with large amounts of prose.
                # A robust way is to select all message contents and take the last one.
                # Claude DOM: `.font-user-message` and `.font-claude-message`.
                # Let's just find the last block of text that looks like a markdown response.
                # Or just grab all text and see if it stabilizes.
                
                # A good selector for Claude's message body is `.grid-cols-1 > div` or similar.
                # Let's try grabbing the raw text content of the `.font-claude-message` classes.
                messages = page.locator('.font-claude-message')
                if messages.count() > 0:
                    current_text = messages.last.inner_text()
                else:
                    # Fallback: grab the last `p` tag's parent container or something similar
                    # It might be `div[data-is-streaming]` but that's risky.
                    # We can use `page.evaluate` to get the last message.
                    current_text = page.evaluate('''() => {
                        const msgs = document.querySelectorAll('.font-claude-message, .break-words');
                        return msgs.length > 0 ? msgs[msgs.length - 1].innerText : "";
                    }''')
                
                if not current_text or len(current_text) < 50:
                    # Still generating initial tokens
                    continue
                    
                if current_text == last_text:
                    stable_count += 1
                else:
                    stable_count = 0
                    last_text = current_text
                    
                if stable_count >= 3:
                    # Unchanged for 3 iterations (6 seconds) = done
                    logger.info(f"Response stabilized at {len(current_text)} chars.")
                    result_text = current_text
                    break
                    
            context.close()
            
    except Exception as e:
        logger.error(f"Playwright automation failed: {e}")
        return None

    if not result_text:
        return None

    # 6. Store in DB
    logger.info("Saving report to database.")
    with LocalSession() as session:
        # Upsert just in case we re-run
        existing = session.query(Report).filter_by(trading_day=trading_day).first()
        if existing:
            existing.content = result_text
            existing.article_ids = article_ids
        else:
            report = Report(
                trading_day=trading_day,
                content=result_text,
                article_ids=article_ids
            )
            session.add(report)
        session.commit()
        
    return result_text
