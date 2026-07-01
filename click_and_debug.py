import os
import sys
import time
import re
from playwright.sync_api import sync_playwright

def get_edge_user_data_dir():
    return os.environ.get("LOCALAPPDATA", "") + r"\Microsoft\Edge\User Data"

def click_and_debug():
    url = "https://brilliant.org/courses/thinking-in-code/first-steps-cs/tappy-onboarding-tic/?from=icp_node&from_llp=computer-science"
    user_data_dir = get_edge_user_data_dir()
    
    print("Launching Edge...")
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
        print("Waiting for page to settle...")
        page.wait_for_timeout(8000)
        
        # Take initial screenshot
        page.screenshot(path=r"D:\internship\myproject\screenshots\step1_initial.png")
        print("Saved step1_initial.png")
        
        # Try to find "Continue" button
        print("\n--- Finding Continue Button ---")
        continue_locs = [
            page.locator("button:has-text('Continue')"),
            page.locator("[role='button']:has-text('Continue')"),
            page.locator("text=Continue").first
        ]
        
        clicked = False
        for loc in continue_locs:
            if loc.count() > 0 and loc.is_visible():
                print(f"Found Continue button using selector: {loc}")
                html = loc.evaluate("el => el.outerHTML")
                print(f"HTML: {html}")
                print("Clicking Continue...")
                loc.click()
                clicked = True
                break
        
        if not clicked:
            print("Could not find Continue button using standard selectors. Let's list all elements containing 'Continue'.")
            all_elements = page.locator("*:has-text('Continue')").all()
            print(f"Found {len(all_elements)} elements containing 'Continue'")
            for idx, el in enumerate(all_elements[:10]):
                try:
                    tag = el.evaluate("el => el.tagName")
                    visible = el.is_visible()
                    html = el.evaluate("el => el.outerHTML")[:100]
                    print(f"  [{idx}] Tag: {tag}, Visible: {visible}, HTML: {html}")
                except Exception as e:
                    print(f"  [{idx}] Error: {e}")
                    
        print("Waiting 5 seconds for next card...")
        page.wait_for_timeout(5000)
        
        # Take second screenshot (should be the question/puzzle screen)
        page.screenshot(path=r"D:\internship\myproject\screenshots\step2_puzzle.png")
        print("Saved step2_puzzle.png")
        
        # Let's inspect the puzzle screen
        print("\n--- Inspecting Puzzle Screen ---")
        # Let's search for interactive elements
        interactives = page.locator("custom-interactive").all()
        print(f"Found {len(interactives)} custom-interactive elements.")
        for idx, intr in enumerate(interactives):
            try:
                auth_name = intr.get_attribute("authored-name")
                test_id = intr.get_attribute("data-testid")
                print(f"  [{idx}] AuthName: {auth_name}, TestID: {test_id}")
                
                # Check for buttons, labels, and text fields inside the shadow root of custom-interactive
                # Playwright supports locator('custom-interactive >> label') or locator('custom-interactive').locator('label')
                # Let's try locating labels or divs inside the custom-interactive
                labels = intr.locator("label").all()
                print(f"    Labels inside shadow DOM: {len(labels)}")
                for j, l in enumerate(labels[:5]):
                    print(f"      [{j}] Text: '{l.inner_text().strip()}', Visible: {l.is_visible()}")
                    
                buttons = intr.locator("button").all()
                print(f"    Buttons inside shadow DOM: {len(buttons)}")
                for j, b in enumerate(buttons[:5]):
                    print(f"      [{j}] Text: '{b.inner_text().strip()}', Visible: {b.is_visible()}")
                    
            except Exception as e:
                print(f"  [{idx}] Error inspecting interactive: {e}")
                
        # Let's also look for all visible buttons on the page
        buttons = page.locator("button").all()
        visible_buttons = [b for b in buttons if b.is_visible()]
        print(f"\nFound {len(visible_buttons)} visible buttons on the page:")
        for idx, btn in enumerate(visible_buttons):
            try:
                text = btn.inner_text().strip().replace('\n', ' ')
                aria = btn.get_attribute("aria-label") or ""
                print(f"  [{idx}] Text: '{text}', Aria-Label: '{aria}', HTML: {btn.evaluate('el => el.outerHTML')[:120]}")
            except Exception:
                pass
                
        context.close()

if __name__ == "__main__":
    click_and_debug()
