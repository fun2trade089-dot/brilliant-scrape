import os
import sys
import time
import re
from playwright.sync_api import sync_playwright

def get_edge_user_data_dir():
    return os.environ.get("LOCALAPPDATA", "") + r"\Microsoft\Edge\User Data"

def test():
    url = "https://brilliant.org/courses/thinking-in-code/first-steps-cs/tappy-onboarding-tic/?from=icp_node&from_llp=computer-science"
    user_data_dir = get_edge_user_data_dir()
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            channel="msedge",
            headless=False,
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled"],
            no_viewport=False,
        )
        page = context.new_page()
        page.goto(url, wait_until="load")
        page.wait_for_timeout(8000)
        
        # Click Continue if it's there
        btn = page.locator("button:has-text('Continue')")
        if btn.count() > 0 and btn.is_visible():
            btn.click()
            page.wait_for_timeout(5000)
            
        # Select options to trigger Check
        choices = page.locator("[class*='draggable']").all()
        if choices:
            choices[0].click()
            page.wait_for_timeout(1000)
            choices[0].click()
            page.wait_for_timeout(1000)
            
        # Click Check
        check_btn = page.locator("button:has-text('Check')").first
        check_btn.click()
        page.wait_for_timeout(4000)
        
        # Click Try Again
        try_again_btn = page.locator("button, a, [role='button']").filter(
            has_text=re.compile(r"try again|try another|reset|clear|try once more|retry", re.IGNORECASE)
        ).first
        try_again_btn.click()
        page.wait_for_timeout(3000)
        
        print("\n--- Inspecting Slot Elements and Icons after Try Again ---")
        
        # Find all elements in the interactive area
        # Let's list all elements containing 'turn' or 'drive'
        elements = page.locator("div, span, svg, button").all()
        for idx, el in enumerate(elements):
            try:
                html = el.evaluate("el => el.outerHTML")
                # Search for incorrect-related keywords in html
                html_lower = html.lower()
                if any(kw in html_lower for kw in ["incorrect", "wrong", "cross", "error", "bad", "invalid", "fail"]):
                    # Print it
                    print(f"[{idx}] Tag: {el.evaluate('el => el.tagName')}, Class: {el.get_attribute('class') or ''}")
                    print(f"    HTML: {html[:250]}")
                    print("-" * 50)
            except Exception:
                pass
                
        context.close()

if __name__ == "__main__":
    test()
