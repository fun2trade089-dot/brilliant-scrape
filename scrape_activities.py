import os
import re
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

def get_urls_from_file(file_path):
    urls = []
    if not os.path.exists(file_path):
        return urls
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            match = re.search(r"https://brilliant.org/practice/[^\s/]+/", line)
            if match:
                urls.append(match.group(0))
    return list(set(urls))

def export_to_txt():
    print("\nExporting successfully scraped content to free_activities.txt...")
    res = supabase.table("activities").select("title, url, content").not_.is_("content", "null").execute()
    
    with open("free_activities.txt", "w", encoding="utf-8") as f:
        f.write("--- BRILLIANT FREE ACTIVITIES CONTENT ---\n\n")
        count = 0
        for item in res.data:
            if item.get("content") and len(item.get("content")) > 0:
                count += 1
                f.write(f"Title: {item['title']}\n")
                f.write(f"URL: {item['url']}\n")
                f.write(f"Content:\n{item['content']}\n")
                f.write("-" * 80 + "\n\n")
    print(f"Exported {count} activities to free_activities.txt")

def scrape_activities():
    urls = get_urls_from_file("activity_urls.txt")
    if not urls:
        print("No URLs found in activity_urls.txt")
        return

    # We only want to process URLs that haven't been successfully scraped yet
    existing = supabase.table("activities").select("url").not_.is_("content", "null").execute()
    existing_urls = [row['url'] for row in existing.data] if existing.data else []
    
    urls_to_process = [u for u in urls if u not in existing_urls]
    
    print(f"Total URLs: {len(urls)} | Already processed: {len(existing_urls)} | Remaining: {len(urls_to_process)}")

    if not urls_to_process:
        export_to_txt()
        return

    with sync_playwright() as p:
        print("Connecting to Browserbase...")
        try:
            browserbase = Browserbase(api_key=BB_API_KEY)
            session = browserbase.sessions.create(project_id=BB_PROJECT_ID)
            browser = p.chromium.connect_over_cdp(session.connect_url)
        except Exception as e:
            print(f"FAILED to connect to Browserbase: {e}")
            return
        
        # Standard desktop Chrome user agent
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        context = browser.new_context(user_agent=user_agent)
        page = context.new_page()

        # Let's process a small batch to test
        batch = urls_to_process[:15]
        
        for url in batch:
            try:
                print(f"Checking: {url}")
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(4000) 
                
                title = page.title()

                if "Home | Brilliant" in title or "Dashboard" in title:
                    print("  -> Locked (Redirected). Skipping.")
                    continue

                content_text = ""
                # Try common interactive containers
                for selector in ["main", ".quiz-container", ".challenge-body", "#__next"]:
                    el = page.query_selector(selector)
                    if el:
                        text = el.inner_text().strip()
                        if len(text) > 50 and "Go Premium" not in text[:100]:
                            content_text = text
                            break
                
                if content_text:
                    clean_text = "\n".join([l.strip() for l in content_text.splitlines() if l.strip()])
                    print(f"  -> SUCCESS: Scraped {len(clean_text)} characters.")
                    
                    supabase.table("activities").update({
                        "content": clean_text
                    }).eq("url", url).execute()
                else:
                    print("  -> No readable text found.")

            except Exception as e:
                print(f"  -> Error: {e}")

        browser.close()
        
    # Generate the text file after the run
    export_to_txt()

if __name__ == "__main__":
    scrape_activities()
