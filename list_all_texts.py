import os
import sys
from playwright.sync_api import sync_playwright

def get_edge_user_data_dir():
    return os.environ.get("LOCALAPPDATA", "") + r"\Microsoft\Edge\User Data"

def search():
    url = "https://brilliant.org/courses/thinking-in-code/first-steps-cs/tappy-onboarding-tic/?from=icp_node&from_llp=computer-science"
    user_data_dir = get_edge_user_data_dir()
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            channel="msedge",
            headless=False,
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled"],
            no_viewport=False,
        )
        page = context.new_page()
        page.goto(url, wait_until="load", timeout=60000)
        page.wait_for_timeout(8000)
        
        # Click Continue if it's there
        btn = page.locator("button:has-text('Continue')")
        if btn.count() > 0 and btn.is_visible():
            btn.click()
            page.wait_for_timeout(5000)
            
        print("Finding all <text> elements in the page (including shadow DOM)...")
        
        # JS to find all text elements
        js_find_texts = """
        () => {
            let results = [];
            function traverse(node) {
                if (!node) return;
                
                // If it's a TEXT tag or contains text content
                let tagName = node.tagName ? node.tagName.toLowerCase() : "";
                if (tagName === "text" || tagName === "tspan" || tagName === "p" || tagName === "span" || tagName === "div" || tagName === "a") {
                    let text = node.textContent ? node.textContent.trim() : "";
                    if (text.length > 0 && text.length < 100) {
                        // Check if it's visible
                        let rect = node.getBoundingClientRect ? node.getBoundingClientRect() : null;
                        let visible = rect ? (rect.width > 0 && rect.height > 0) : false;
                        if (visible) {
                            results.push({
                                tagName: node.tagName,
                                className: node.className || "",
                                text: text,
                                rect: rect ? {x: rect.x, y: rect.y, width: rect.width, height: rect.height} : null
                            });
                        }
                    }
                }
                
                // Recurse children
                if (node.children) {
                    for (let child of node.children) {
                        traverse(child);
                    }
                }
                
                // Recurse shadow DOM
                if (node.shadowRoot) {
                    traverse(node.shadowRoot);
                }
            }
            traverse(document.documentElement);
            return results;
        }
        """
        
        texts = page.evaluate(js_find_texts)
        print(f"Found {len(texts)} visible text elements:")
        for idx, t in enumerate(texts):
            # Print if it contains "turn" or "left" or "drive" or "forward"
            lower_text = t['text'].lower()
            if any(w in lower_text for w in ["turn", "left", "drive", "forward"]):
                print(f"[{idx}] Tag: {t['tagName']}, Class: {t['className']}, Text: '{t['text']}'")
                print(f"    Coords: {t['rect']}")
                print("-" * 50)
                
        context.close()

if __name__ == "__main__":
    search()
