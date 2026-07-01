import os
import re
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

SESSION_ID = os.getenv("BRILLIANT_SESSION_ID")
CSRF_TOKEN = os.getenv("BRILLIANT_CSRF_TOKEN")

def get_preview_links(file_path):
    links = []
    if not os.path.exists(file_path):
        return links
        
    current_course = "Unknown Course"
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("Course: "):
                current_course = line.replace("Course: ", "").strip()
            elif line.startswith("Preview URL: "):
                url = line.replace("Preview URL: ", "").strip()
                links.append({"course": current_course, "url": url})
    return links

def record_previews():
    preview_data = get_preview_links("free_previews.txt")
    if not preview_data:
        return

    base_dir = "D:\\internship\\myproject\\recordings"
    os.makedirs(base_dir, exist_ok=True)

    with sync_playwright() as p:
        print("Launching Local Browser for Recording...")
        browser = p.chromium.launch(headless=True) 

        # Testing just the first one to debug the "stuck on start page" issue
        for item in preview_data[:1]:
            course_name = item['course']
            url = item['url']
            
            safe_course_name = "".join([c if c.isalnum() else "_" for c in course_name])
            clean_url = url.split('?')[0].rstrip('/')
            slug = [s for s in clean_url.split("/") if s][-1]
            raw_title = f"Preview_{slug}"
            safe_title = "".join([c for c in raw_title if c.isalnum() or c in ['_', '-']])
            
            course_dir = os.path.join(base_dir, safe_course_name)
            os.makedirs(course_dir, exist_ok=True)
            
            print(f"\n>>> Recording Preview for: {course_name}")
            print(f"URL: {url}")

            context = browser.new_context(
                viewport={'width': 1280, 'height': 800},
                record_video_dir=course_dir,
                record_video_size={'width': 1280, 'height': 800}
            )

            if SESSION_ID:
                context.add_cookies([
                    {"name": "sessionid", "value": SESSION_ID, "domain": ".brilliant.org", "path": "/"},
                    {"name": "csrftoken", "value": CSRF_TOKEN, "domain": ".brilliant.org", "path": "/"}
                ])

            page = context.new_page()

            try:
                page.goto(url, wait_until="load", timeout=60000)
                print("  Waiting 5s for page to settle...")
                page.wait_for_timeout(5000)

                # --- NEW LOGIC: Check for a "Start" or "Continue" button ---
                print("  Checking if we are stuck on a landing page...")
                start_buttons = [
                    page.get_by_role("button", name="Start"),
                    page.get_by_role("button", name="Continue"),
                    page.get_by_text("Start Course").first,
                    page.locator("a:has-text('Start')").first
                ]
                
                clicked_start = False
                for btn in start_buttons:
                    if btn.is_visible():
                        print(f"  Action: Found a start button, clicking it...")
                        btn.click()
                        page.wait_for_timeout(5000) # wait for next page to load
                        clicked_start = True
                        break
                
                if not clicked_start:
                    print("  No obvious start button found. Assuming we are on the activity.")

                # Click Koji
                print("  Action: Clicking Koji at 40, 760...")
                page.mouse.click(40, 760)
                
                print("  Action: Recording interaction for 20 seconds...")
                page.wait_for_timeout(20000)

                video = page.video
                video_path = video.path() if video else None

            except Exception as e:
                print(f"  Error during recording: {e}")
                video_path = None

            context.close()
            print("  Context closed, finalizing video...")
            
            if video_path and os.path.exists(video_path):
                final_path = os.path.join(course_dir, f"{safe_title}.webm")
                if os.path.exists(final_path):
                    os.remove(final_path)
                os.rename(video_path, final_path)
                print(f"  SUCCESS: Video saved to {final_path}")

        browser.close()

if __name__ == "__main__":
    record_previews()
