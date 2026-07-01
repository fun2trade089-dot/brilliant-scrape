import os
import time
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

# 1. Credentials from your .env file
SESSION_ID = os.getenv("BRILLIANT_SESSION_ID")
CSRF_TOKEN = os.getenv("BRILLIANT_CSRF_TOKEN")

def solve_activity():
    url = "https://brilliant.org/courses/pixel-pusher/intro-to-functions/pp-returning-values/?from=icp_node&from_llp=computer-science#page-1"
    
    with sync_playwright() as p:
        print("Launching browser...")
        # Use a real user data dir or standard launch
        browser = p.chromium.launch(headless=False, slow_mo=500) # slow_mo helps us see the actions
        
        context = browser.new_context()
        context.add_cookies([
            {"name": "sessionid", "value": SESSION_ID, "domain": ".brilliant.org", "path": "/"},
            {"name": "csrftoken", "value": CSRF_TOKEN, "domain": ".brilliant.org", "path": "/"}
        ])
        
        page = context.new_page()
        print(f"Navigating to: {url}")
        
        try:
            page.goto(url, wait_until="load")
            
            # 1. Check if we got kicked to the dashboard
            page.wait_for_timeout(5000)
            print(f"Page Title: {page.title()}")
            
            if "Home | Brilliant" in page.title() or "Dashboard" in page.title():
                print("--- CRITICAL ERROR: You were REDIRECTED to the Home page. ---")
                print("This means your SESSION_ID in .env is incorrect or expired.")
                print("Please log in to Brilliant in your Chrome browser and get a FRESH sessionid.")
                time.sleep(5)
                return

            # 2. Locate the Elements
            print("Searching for puzzle elements...")
            
            # --- DISCOVERY: Let's see what text is actually on the page ---
            all_text = page.locator("button, span, div").all_inner_texts()
            # Filter for the relevant math strings
            relevant_finds = [t.strip() for t in all_text if "pixel" in t]
            print(f"DEBUG: Found these 'pixel' related strings: {relevant_finds}")

            # Source: The answer block
            # We try multiple ways to find the '255 - pixel' block
            # Using a more flexible regex-based search
            source = page.get_by_text("255 - pixel", exact=False).first
            if not source.is_visible():
                # Try finding by looking for any element containing the text
                source = page.locator("*:has-text('255 - pixel')").last
            
            # Target: The empty box
            target_id = "LessonPpReturningValuesV12Problem1Solvable/slot_line_2_condition"
            target = page.locator(f"id={target_id}")


            # Check visibility
            is_source_there = source.is_visible()
            is_target_there = target.is_visible()
            
            print(f"DEBUG: '255 - pixel' block found: {is_source_there}")
            print(f"DEBUG: Empty drop box found: {is_target_there}")

            if is_source_there and is_target_there:
                # 3. Perform the Action
                print("ACTION: Dragging and Dropping...")
                # We do it step-by-step for reliability
                source.hover()
                page.mouse.down()
                target.hover()
                page.mouse.up()
                
                print("Action complete. Waiting 2 seconds for animation...")
                time.sleep(2)

                # 4. Submit the answer
                print("ACTION: Clicking 'Check'...")
                check_button = page.get_by_role("button", name="Check")
                if check_button.is_visible():
                    check_button.click()
                    print("--- SUCCESS: Puzzle solved! ---")
                else:
                    print("ERROR: Could not find the 'Check' button.")
            else:
                if not is_source_there:
                    print("ERROR: Could not see the '255 - pixel' block. Is it a different puzzle today?")
                if not is_target_there:
                    print(f"ERROR: Could not see the box with ID '{target_id}'. The website might have changed its code.")

        except Exception as e:
            print(f"AN UNEXPECTED ERROR OCCURRED: {e}")

        print("\nScript finished. Keeping browser open for 15 seconds for you to check...")
        time.sleep(15)
        browser.close()

if __name__ == "__main__":
    if not SESSION_ID:
        print("ERROR: No BRILLIANT_SESSION_ID found in .env")
    else:
        solve_activity()
