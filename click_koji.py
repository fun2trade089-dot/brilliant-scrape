import os
import time
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

SESSION_ID = os.getenv("BRILLIANT_SESSION_ID")
CSRF_TOKEN = os.getenv("BRILLIANT_CSRF_TOKEN")

def click_koji_exact():
    url = "https://brilliant.org/courses/pixel-pusher/intro-to-functions/pp-returning-values/?from=icp_node&from_llp=computer-science#page-1"
    
    with sync_playwright() as p:
        print("Launching browser...")
        # Keeping slow_mo so you can see the chat open clearly
        browser = p.chromium.launch(headless=False, slow_mo=500) 
        
        context = browser.new_context()
        if SESSION_ID:
            context.add_cookies([
                {"name": "sessionid", "value": SESSION_ID, "domain": ".brilliant.org", "path": "/"},
                {"name": "csrftoken", "value": CSRF_TOKEN, "domain": ".brilliant.org", "path": "/"}
            ])
        
        page = context.new_page()
        # MUST keep this exact size so 40,760 stays accurate
        page.set_viewport_size({"width": 1280, "height": 800})
        
        print(f"Navigating to: {url}")
        try:
            page.goto(url, wait_until="load")
            print("Waiting for page to settle (10 seconds)...")
            page.wait_for_timeout(10000) 
            
            # The exact coordinates you verified!
            x_coord = 40
            y_coord = 760
            
            print(f"\nACTION: Moving mouse to exact Koji coordinates ({x_coord}, {y_coord})")
            page.mouse.move(x_coord, y_coord)
            
            print("ACTION: Clicking to open Koji...")
            page.mouse.click(x_coord, y_coord)
            
            print("SUCCESS: Koji should now be open!")
            
            # Wait to let you read the hint or chat
            print("Waiting 15 seconds before closing...")
            page.wait_for_timeout(15000)

        except Exception as e:
            print(f"Error: {e}")

        print("Process finished.")
        browser.close()

if __name__ == "__main__":
    click_koji_exact()
