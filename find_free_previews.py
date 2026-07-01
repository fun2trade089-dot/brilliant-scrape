import os
from playwright.sync_api import sync_playwright
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

SESSION_ID = os.getenv("BRILLIANT_SESSION_ID")
CSRF_TOKEN = os.getenv("BRILLIANT_CSRF_TOKEN")

def find_free_course_previews():
    print("Fetching course landing pages from database...")
    res = supabase.table("courses").select("title, url").execute()
    courses = res.data

    if not courses:
        print("No courses found in database.")
        return

    print(f"Total courses to check: {len(courses)}")
    
    with open("free_previews.txt", "w", encoding="utf-8") as f:
        f.write("--- FREE COURSE PREVIEW LINKS ---\n\n")

    with sync_playwright() as p:
        print("Launching Browser...")
        # Running headless for speed, since landing pages are public
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        
        # Inject cookies just in case the preview behavior changes based on login
        if SESSION_ID:
            context.add_cookies([
                {"name": "sessionid", "value": SESSION_ID, "domain": ".brilliant.org", "path": "/"},
                {"name": "csrftoken", "value": CSRF_TOKEN, "domain": ".brilliant.org", "path": "/"}
            ])
            
        page = context.new_page()

        found_count = 0
        
        for course in courses:
            course_url = course['url']
            print(f"Checking course: {course['title']}...")
            
            try:
                page.goto(course_url, wait_until="domcontentloaded", timeout=30000)
                
                # We are looking for the main "Start Course" or "Continue" button link
                # Brilliant usually uses an anchor tag styled as a button for the first lesson
                
                # Strategy 1: Look for links inside the first 'chapter' section
                preview_link = None
                
                # Look for typical 'Start' buttons or links that point to the actual lessons (not just anchors)
                hrefs = page.locator("a[href*='/courses/']").all()
                for href_locator in hrefs:
                    link = href_locator.get_attribute("href")
                    # We want links that look like a lesson path (e.g., /courses/math/chapter/lesson/), 
                    # not just a link back to the main course page
                    if link and len(link.split('/')) > 4 and "practice" not in link:
                        preview_link = link
                        break

                if preview_link:
                    full_link = f"https://brilliant.org{preview_link}" if preview_link.startswith("/") else preview_link
                    print(f"  -> Found Preview Link: {full_link}")
                    found_count += 1
                    
                    with open("free_previews.txt", "a", encoding="utf-8") as f:
                        f.write(f"Course: {course['title']}\n")
                        f.write(f"Preview URL: {full_link}\n")
                        f.write("-" * 40 + "\n")
                else:
                    print("  -> No distinct preview link found on landing page.")
                    
            except Exception as e:
                print(f"  -> Error checking course: {e}")

        browser.close()
        print(f"\nDone! Found {found_count} free preview links.")
        print("Check 'free_previews.txt' for the list.")

if __name__ == "__main__":
    find_free_course_previews()
