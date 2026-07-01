import os
import sys
import time
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
            
        # Click options to fill slots
        choices = page.locator("[class*='draggable']").all()
        print(f"Initially found {len(choices)} draggable choices.")
        if choices:
            choices[0].click()
            page.wait_for_timeout(1000)
            choices[0].click()
            page.wait_for_timeout(1000)
            
        print("\n--- Inspecting [class*='draggable'] elements after filling slots ---")
        current_choices = page.locator("[class*='draggable']").all()
        print(f"Now found {len(current_choices)} draggable choices:")
        for idx, el in enumerate(current_choices):
            try:
                html = el.evaluate("el => el.outerHTML")
                text = el.inner_text().strip().replace('\n', ' ')
                bbox = el.bounding_box()
                print(f"[{idx}] Text: '{text}', Box: {bbox}")
                print(f"    HTML: {html[:200]}")
                print("-" * 50)
            except Exception as e:
                print(f"[{idx}] Error: {e}")
                
        context.close()

if __name__ == "__main__":
    test()
