import os
import sys
import json
from playwright.sync_api import sync_playwright

def get_edge_user_data_dir():
    return os.environ.get("LOCALAPPDATA", "") + r"\Microsoft\Edge\User Data"

def inspect():
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
            
        print("Dumping Shadow DOM for custom-interactive elements...")
        
        # JS function to dump the tree recursively including shadow DOM
        js_dump = """
        () => {
            function dumpNode(node) {
                let info = {
                    tagName: node.tagName,
                    id: node.id || "",
                    className: node.className || "",
                    role: node.getAttribute ? node.getAttribute("role") : "",
                    ariaLabel: node.getAttribute ? node.getAttribute("aria-label") : "",
                    text: (node.childNodes.length === 1 && node.childNodes[0].nodeType === 3) ? node.textContent.trim() : "",
                    children: []
                };
                
                // Add attributes of interest
                if (node.getAttribute) {
                    let attrs = ["data-testid", "authored-name", "disabled", "type", "class", "style"];
                    info.attrs = {};
                    for (let a of attrs) {
                        let v = node.getAttribute(a);
                        if (v !== null) info.attrs[a] = v;
                    }
                }

                // Recurse children
                for (let child of node.children) {
                    info.children.push(dumpNode(child));
                }

                // Recurse shadowRoot
                if (node.shadowRoot) {
                    info.shadowRoot = [];
                    for (let child of node.shadowRoot.children) {
                        info.shadowRoot.push(dumpNode(child));
                    }
                }

                return info;
            }

            let interactives = document.querySelectorAll("custom-interactive");
            return Array.from(interactives).map(dumpNode);
        }
        """
        
        result = page.evaluate(js_dump)
        print(json.dumps(result, indent=2))
        
        # Save JSON to file
        with open("shadow_dom_dump.json", "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print("Saved shadow DOM tree to shadow_dom_dump.json")
        
        context.close()

if __name__ == "__main__":
    inspect()
