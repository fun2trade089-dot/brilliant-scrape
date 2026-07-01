import os
import sys
import time
from playwright.sync_api import sync_playwright

def get_edge_user_data_dir():
    return os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\Edge\User Data")

def debug():
    url = "https://brilliant.org/courses/thinking-in-code/first-steps-cs/tappy-onboarding-tic/?from=icp_node&from_llp=computer-science"
    user_data_dir = get_edge_user_data_dir()
    
    print("Launching Edge to debug selectors...")
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
        print(f"Navigating to {url}...")
        page.goto(url, wait_until="load", timeout=60000)
        print("Waiting 10 seconds for page to settle...")
        page.wait_for_timeout(10000)
        
        print("\n--- Inspecting page structure for choice/option elements ---")
        
        # 1. Look for all elements that might be choices
        selectors = [
            "custom-interactive label",
            "[role='radio']",
            "[role='checkbox']",
            "button[role='checkbox']",
            "button[role='radio']",
            "[class*='choice']",
            "[class*='option']",
            "label",
            "button",
            "custom-interactive"
        ]
        
        for sel in selectors:
            elements = page.locator(sel).all()
            print(f"Selector '{sel}': found {len(elements)} elements")
            for i, el in enumerate(elements[:5]):
                try:
                    tag = el.evaluate("el => el.tagName")
                    text = el.inner_text().strip().replace('\n', ' ')
                    html = el.evaluate("el => el.outerHTML")[:150]
                    visible = el.is_visible()
                    print(f"  [{i}] Tag: {tag}, Visible: {visible}, Text: '{text[:50]}'")
                    print(f"      HTML: {html}")
                except Exception as e:
                    print(f"  [{i}] Error: {e}")
        
        # Save a screenshot
        screenshot_path = r"D:\internship\myproject\screenshots\debug_choices.png"
        os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
        page.screenshot(path=screenshot_path)
        print(f"\nSaved screenshot to {screenshot_path}")
        
        print("\nClosing browser...")
        context.close()

if __name__ == "__main__":
    debug()
