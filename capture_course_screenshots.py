import os
import re
from playwright.sync_api import sync_playwright
from browserbase import Browserbase
from dotenv import load_dotenv

load_dotenv()

BB_API_KEY = os.getenv("BROWSERBASE_API_KEY")
BB_PROJECT_ID = os.getenv("BROWSERBASE_PROJECT_ID")

def get_course_urls(file_path):
    urls = []
    if not os.path.exists(file_path):
        return urls
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            match = re.search(r"URL: (https://brilliant.org/courses/[^\s/]+/?)$", line)
            if match:
                urls.append(match.group(1))
    return list(set(urls))

def capture_course_screenshots():
    urls = get_course_urls("courses.txt")
    if not urls:
        print("No URLs found in courses.txt")
        return

    print(f"Found {len(urls)} course URLs.")

    output_dir = "screenshots/Courses"
    os.makedirs(output_dir, exist_ok=True)

    with sync_playwright() as p:
        print("Connecting to Browserbase...")
        try:
            browserbase = Browserbase(api_key=BB_API_KEY)
            session = browserbase.sessions.create(project_id=BB_PROJECT_ID)
            browser = p.chromium.connect_over_cdp(session.connect_url)
        except Exception as e:
            print(f"FAILED to connect to Browserbase: {e}")
            return
        
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        # Limit to 5 for now
        for url in urls[:5]:
            try:
                # Extract course slug for filename
                slug = url.strip("/").split("/")[-1]
                file_path = os.path.join(output_dir, f"{slug}.png")
                
                print(f"\nCapturing: {url}")
                page.goto(url, wait_until="networkidle", timeout=60000)
                page.wait_for_timeout(5000)
                
                page.screenshot(path=file_path, full_page=True)
                print(f"  -> SUCCESS: Saved to {file_path}")

            except Exception as e:
                print(f"  -> Error: {e}")

        browser.close()
        print(f"\nDone. Screenshots saved in '{output_dir}'.")

if __name__ == "__main__":
    capture_course_screenshots()
