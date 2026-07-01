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
            
        print("Searching entire page DOM for elements containing 'turn left' or 'drive forward'...")
        
        # JS to search all elements
        js_search = """
        () => {
            function findInTree(root) {
                let results = [];
                
                function recurse(node) {
                    if (!node) return;
                    
                    // Check if node itself matches
                    let has_text = false;
                    let text = "";
                    if (node.childNodes && node.childNodes.length > 0) {
                        for (let child of node.childNodes) {
                            if (child.nodeType === 3) { // Text node
                                let val = child.textContent.trim().toLowerCase();
                                if (val.includes("turn left") || val.includes("drive forward")) {
                                    has_text = true;
                                    text = child.textContent.trim();
                                    break;
                                }
                            }
                        }
                    }
                    
                    if (has_text) {
                        results.push({
                            tagName: node.tagName,
                            id: node.id || "",
                            className: node.className || "",
                            text: text,
                            outerHTML: node.outerHTML.substring(0, 300)
                        });
                    }
                    
                    // Recurse children
                    if (node.children) {
                        for (let child of node.children) {
                            recurse(child);
                        }
                    }
                    
                    // Recurse shadow DOM
                    if (node.shadowRoot) {
                        recurse(node.shadowRoot);
                    }
                }
                
                recurse(root);
                return results;
            }
            
            return findInTree(document.documentElement);
        }
        """
        
        results = page.evaluate(js_search)
        for idx, res in enumerate(results):
            print(f"[{idx}] Tag: {res['tagName']}, Class: {res['className']}, ID: {res['id']}")
            print(f"    Text: '{res['text']}'")
            print(f"    HTML: {res['outerHTML']}")
            print("-" * 50)
            
        context.close()

if __name__ == "__main__":
    search()
