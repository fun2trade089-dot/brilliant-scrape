import os
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

SESSION_ID = os.getenv("BRILLIANT_SESSION_ID")
CSRF_TOKEN = os.getenv("BRILLIANT_CSRF_TOKEN")

def test_redirect():
    url = "https://brilliant.org/practice/quotient-rule-practice-set-1/"
    print(f"Testing URL: {url}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        context.add_cookies([
            {"name": "sessionid", "value": SESSION_ID, "domain": ".brilliant.org", "path": "/"},
            {"name": "csrftoken", "value": CSRF_TOKEN, "domain": ".brilliant.org", "path": "/"}
        ])
        page = context.new_page()
        
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(3000)
        
        print(f"Final URL: {page.url}")
        print(f"Final Title: {page.title()}")
        browser.close()

if __name__ == "__main__":
    test_redirect()
