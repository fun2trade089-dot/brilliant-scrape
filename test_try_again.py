import os
import sys
import time
import re
from playwright.sync_api import sync_playwright

def get_edge_user_data_dir():
    return os.environ.get("LOCALAPPDATA", "") + r"\Microsoft\Edge\User Data"

def test_try_again_behavior():
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
            
        # Select choices to enable Check button
        choices = page.locator("[class*='draggable']").all()
        print(f"Found {len(choices)} draggable options.")
        
        # Click the first option
        if choices:
            choices[0].click()
            page.wait_for_timeout(1000)
        # Click the second option (might be same or different)
        if len(choices) > 1:
            choices[1].click()
            page.wait_for_timeout(1000)
        else:
            choices[0].click()
            page.wait_for_timeout(1000)
            
        page.screenshot(path=r"D:\internship\myproject\screenshots\debug_try_again_1_selected.png")
        print("Saved debug_try_again_1_selected.png")
        
        # Click Check
        check_btn = page.locator("button:has-text('Check')").first
        print(f"Check Button Enabled: {check_btn.is_enabled()}")
        check_btn.click()
        page.wait_for_timeout(4000)
        
        page.screenshot(path=r"D:\internship\myproject\screenshots\debug_try_again_2_checked.png")
        print("Saved debug_try_again_2_checked.png")
        
        # Click Try Again
        try_again_btn = page.locator("button, a, [role='button']").filter(
            has_text=re.compile(r"try again|try another|reset|clear|try once more|retry", re.IGNORECASE)
        ).first
        
        print(f"Try Again Button Visible: {try_again_btn.is_visible()}")
        print("Clicking Try Again...")
        try_again_btn.click()
        page.wait_for_timeout(4000)
        
        page.screenshot(path=r"D:\internship\myproject\screenshots\debug_try_again_3_after_reset.png")
        print("Saved debug_try_again_3_after_reset.png")
        
        # Check if Check is still enabled
        check_btn = page.locator("button:has-text('Check')").first
        print(f"Check Button Enabled after reset: {check_btn.is_enabled()}")
        
        context.close()

if __name__ == "__main__":
    test_try_again_behavior()
