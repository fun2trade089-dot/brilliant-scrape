import os
import sys
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
            
        print("Checking Check button properties...")
        check_btn = page.locator("button:has-text('Check')").first
        
        is_visible = check_btn.is_visible()
        is_enabled = check_btn.is_enabled()
        html = check_btn.evaluate("el => el.outerHTML")
        disabled_attr = check_btn.get_attribute("disabled")
        
        print(f"Check Button: Visible={is_visible}, Enabled={is_enabled}, DisabledAttr={disabled_attr}")
        print(f"HTML: {html}")
        
        context.close()

if __name__ == "__main__":
    test()
