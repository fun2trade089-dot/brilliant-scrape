import os
from playwright.sync_api import sync_playwright
from browserbase import Browserbase
from dotenv import load_dotenv

load_dotenv()

BB_API_KEY = os.getenv("BROWSERBASE_API_KEY")
BB_PROJECT_ID = os.getenv("BROWSERBASE_PROJECT_ID")

def capture_single_url():
    url = "https://brilliant.org/courses/pixel-pusher/intro-to-functions/pp-returning-values/?from=icp_node&from_llp=computer-science#page-1"
    
    print(f"Target URL: {url}")
    
    output_dir = "/mnt/d/internship/myproject/screenshots/SingleTest"
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, "pp-returning-values.png")

    with sync_playwright() as p:
        print("Connecting to Browserbase...")
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
            print(f"Attempting to load page...")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # Wait for content to render, especially interactive canvas or WebGL
            print("Waiting for interactive content to render (10 seconds)...")
            page.wait_for_timeout(10000) 
            
            page_title = page.title()
            print(f"Page Title: {page_title}")
            
            if "Home | Brilliant" in page_title or "Dashboard" in page_title:
                print("-> Redirected to Home/Dashboard. The content is locked or requires login.")
            
            page.screenshot(path=file_path, full_page=False)
            print(f"-> SUCCESS: Screenshot saved to {file_path}")

        except Exception as e:
            print(f"-> Error: {e}")

        browser.close()

if __name__ == "__main__":
    capture_single_url()
