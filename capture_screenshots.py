import os
from playwright.sync_api import sync_playwright
from browserbase import Browserbase
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Setup Clients
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

BB_API_KEY = os.getenv("BROWSERBASE_API_KEY")
BB_PROJECT_ID = os.getenv("BROWSERBASE_PROJECT_ID")

def capture_course_screenshots(target_course_name):
    print(f"Targeting course: {target_course_name}")
    
    courses_res = supabase.table("courses").select("id, title").eq("title", target_course_name).execute()
    courses = courses_res.data
    
    if not courses:
        print(f"Course '{target_course_name}' not found in database.")
        return

    course_id = courses[0]['id']
    print(f"Found course ID: {course_id}")

    act_res = supabase.table("activities").select("title, url").eq("course_id", course_id).execute()
    activities = act_res.data

    if not activities:
        print("No activities found for this course.")
        return

    print(f"Found {len(activities)} activities to capture.")

    base_dir = "/mnt/d/internship/myproject/screenshots"
    safe_course_name = "".join([c if c.isalnum() else "_" for c in target_course_name])
    course_dir = os.path.join(base_dir, safe_course_name)
    os.makedirs(course_dir, exist_ok=True)

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

        total_captured = 0
        for activity in activities:
            url = activity['url']
            title = activity['title']
            safe_title = "".join([c if c.isalnum() else "_" for c in title])
            file_name = f"{safe_title}.png"
            file_path = os.path.join(course_dir, file_name)

            if os.path.exists(file_path):
                print(f"  - Skipping {title} (already exists)")
                continue

            try:
                print(f"  Attempting: {title}")
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(6000) 
                
                page_title = page.title()
                if "Home | Brilliant" in page_title or "Dashboard" in page_title:
                    print("    -> Locked. Skipping.")
                    continue

                page.screenshot(path=file_path, full_page=False)
                print(f"    -> SUCCESS: Saved to {file_path}")
                total_captured += 1

            except Exception as e:
                print(f"    -> Error: {e}")

        browser.close()
        print(f"\nDONE! Captured {total_captured} screenshots for {target_course_name}.")
        print(f"You can find them in: {course_dir}")

if __name__ == "__main__":
    capture_course_screenshots("Programming with Functions")
