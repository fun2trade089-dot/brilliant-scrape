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

def find_truly_free_activities_local():
    print("Fetching activities from database...")
    res = supabase.table("activities").select("id, title, url").execute()
    all_activities = res.data

    if not all_activities:
        print("No activities found in database.")
        return

    # Let's test the first 20 locally to see if it bypasses the block
    batch_to_check = all_activities[:20] 
    
    print(f"Testing {len(batch_to_check)} links locally...")
    
    with open("verified_free_activities_local.txt", "w", encoding="utf-8") as f:
        f.write("--- VERIFIED FREE ACTIVITIES (LOCAL BROWSER) ---\n\n")

    with sync_playwright() as p:
        print("Launching Local Chrome Browser...")
        # headless=False means you will actually see the browser open and click through!
        # This makes it look much more like a real human to Brilliant.
        browser = p.chromium.launch(headless=False)
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        
        if SESSION_ID:
            context.add_cookies([
                {"name": "sessionid", "value": SESSION_ID, "domain": ".brilliant.org", "path": "/"},
                {"name": "csrftoken", "value": CSRF_TOKEN, "domain": ".brilliant.org", "path": "/"}
            ])
            
        page = context.new_page()

        free_count = 0
        total_checked = 0
        
        for activity in batch_to_check:
            total_checked += 1
            target_url = activity['url']
            print(f"Checking {total_checked}: {activity['title']}...")
            
            try:
                page.goto(target_url, wait_until="load", timeout=30000)
                page.wait_for_timeout(3000) 
                
                current_url = page.url
                
                clean_target = target_url.rstrip('/')
                clean_current = current_url.split('#')[0].rstrip('/')
                
                if clean_target in clean_current:
                    print(f"  -> SUCCESS! Found Free Activity.")
                    free_count += 1
                    
                    with open("verified_free_activities_local.txt", "a", encoding="utf-8") as f:
                        f.write(f"ID: {activity['id']} | Title: {activity['title']}\n")
                        f.write(f"URL: {target_url}\n")
                        f.write("-" * 40 + "\n")
                else:
                    print("  -> Redirected. Locked.")
                    
            except Exception as e:
                print(f"  -> Error: {e}")

        browser.close()
        print(f"\nDone! Found {free_count} free activities locally.")

if __name__ == "__main__":
    find_truly_free_activities_local()
