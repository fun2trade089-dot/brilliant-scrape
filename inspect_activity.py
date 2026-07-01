import os
import time
from playwright.sync_api import sync_playwright
from browserbase import Browserbase
from dotenv import load_dotenv

load_dotenv()

BB_API_KEY = os.getenv("BROWSERBASE_API_KEY")
BB_PROJECT_ID = os.getenv("BROWSERBASE_PROJECT_ID")

def inspect_drag_and_drop():
    url = "https://brilliant.org/courses/pixel-pusher/intro-to-functions/pp-returning-values/?from=icp_node&from_llp=computer-science#page-1"
    
    with sync_playwright() as p:
        print("Connecting to Browserbase to inspect page structure...")
        try:
            browserbase = Browserbase(api_key=BB_API_KEY)
            session = browserbase.sessions.create(project_id=BB_PROJECT_ID)
            browser = p.chromium.connect_over_cdp(session.connect_url)
        except Exception as e:
            print(f"FAILED to connect to Browserbase: {e}")
            return
        
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()

        try:
            page.goto(url, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(5000) 
            
            # Print out the text of potential draggable items
            print("\n--- Identifying Potential Draggable Items ---")
            # Brilliant often uses role="button" or specific classes for these
            elements = page.locator("div, span, button").all_inner_texts()
            
            # This is a very rough dump, but helps us guess selectors
            unique_texts = list(set([t.strip() for t in elements if t.strip() and len(t.strip()) < 50]))
            for text in unique_texts[:20]:
                print(f"Found text: '{text}'")

            # Take a screenshot so I can "see" what needs to be dragged
            file_path = "/mnt/d/internship/myproject/screenshots/SingleTest/drag_drop_inspect.png"
            page.screenshot(path=file_path)
            print(f"\nSaved screenshot to {file_path} for manual review.")

        except Exception as e:
            print(f"Error: {e}")

        browser.close()

if __name__ == "__main__":
    inspect_drag_and_drop()
