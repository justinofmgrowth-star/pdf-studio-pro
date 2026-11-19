import os
import time
import json
import re
from typing import Dict, Any, Optional
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.join(BASE_DIR, "deepseek_browser_profile")
os.makedirs(PROFILE_DIR, exist_ok=True)

COMMON_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-infobars",
    "--start-maximized"
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

def open_login_window():
    """
    Opens real Google Chrome in visible mode for manual login.
    CloudFront anti-bot flags are completely removed.
    """
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            channel="chrome",
            headless=False,
            ignore_default_args=["--enable-automation"],
            args=COMMON_ARGS,
            user_agent=USER_AGENT,
            viewport=None
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page.goto("https://chat.deepseek.com", wait_until="domcontentloaded")

        print("Real Chrome khul gaya hai. Login hone ke baad browser window band kar dein...")
        # Keep open until the user manually closes the window
        while len(context.pages) > 0:
            try:
                page.wait_for_timeout(1000)
            except Exception:
                break
        context.close()

def ask_deepseek_web(prompt: str, show_browser: bool = False, timeout_sec: int = 150) -> str:
    """
    Automates chat.deepseek.com using real Google Chrome channel & anti-detection.
    Types prompt, monitors streaming, and scrapes markdown content.
    """
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            channel="chrome",
            headless=not show_browser,
            ignore_default_args=["--enable-automation"],
            args=COMMON_ARGS,
            user_agent=USER_AGENT,
            viewport=None if show_browser else {"width": 1280, "height": 800}
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        page.goto("https://chat.deepseek.com", wait_until="domcontentloaded", timeout=45000)
        time.sleep(3)

        # Check if redirected to sign_in
        if "sign_in" in page.url or page.locator("input[type='password']").count() > 0:
            context.close()
            raise RuntimeError(
                "Aapka DeepSeek account login nahi hai! "
                "Pehle left sidebar me 'Open DeepSeek Web to Login' button daba kar login karein."
            )

        # Find chat input textarea
        selectors = [
            "#chat-input",
            "textarea",
            "div[contenteditable='true']",
            "textarea[placeholder*='DeepSeek']"
        ]
        input_element = None
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=3000):
                    input_element = loc
                    break
            except Exception:
                continue

        if not input_element:
            context.close()
            raise RuntimeError(
                "DeepSeek Chatbox nahi mila! Please sidebar me 'Open DeepSeek Web to Login' button daba kar login check karein."
            )

        # Fill prompt
        input_element.fill(prompt)
        time.sleep(1)

        # Press Enter or click send button
        input_element.press("Enter")

        # In case Enter alone didn't send, trigger click on send icon
        time.sleep(1)
        send_btns = page.locator("div[role='button']:has(svg), button:has(svg), .send-button")
        for i in range(min(send_btns.count(), 3)):
            try:
                b = send_btns.nth(i)
                if b.is_visible():
                    b.click(timeout=1000)
                    break
            except Exception:
                pass

        print("DeepSeek is generating response...")
        start_time = time.time()
        last_text = ""
        stable_count = 0

        # Wait 4 seconds for generation to start
        time.sleep(4)

        while (time.time() - start_time) < timeout_sec:
            # Check response elements
            messages = page.locator(".ds-markdown, .markdown, div[class*='markdown']")
            count = messages.count()

            if count > 0:
                current_text = messages.last.inner_text().strip()
                if current_text and current_text == last_text:
                    stable_count += 1
                    # If text stopped changing for 4 consecutive intervals (~6 sec), generation complete
                    if stable_count >= 4:
                        break
                else:
                    stable_count = 0
                    last_text = current_text

            time.sleep(1.5)

        context.close()

        if not last_text:
            raise RuntimeError("DeepSeek se content scrape nahi ho saka. Dobara koshish karein.")

        return last_text
