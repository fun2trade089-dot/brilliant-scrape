import json

def find_text(node, term, path=""):
    node_tag = node.get('tagName', '')
    node_id = node.get('id', '')
    node_class = node.get('className', '')
    node_text = node.get('text', '')
    node_attrs = node.get('attrs', {})
    
    current_path = f"{path} -> {node_tag}(class={node_class}, id={node_id})"
    
    # Check text or ariaLabel or some attribute
    match = False
    if term in node_text.lower():
        match = True
    if 'ariaLabel' in node and term in (node['ariaLabel'] or '').lower():
        match = True
    
    if match:
        print(f"FOUND Match for '{term}':")
        print(f"  Path: {current_path}")
        print(f"  Attrs: {node_attrs}")
        print(f"  Text: '{node_text}'")
        
    for c in node.get('children', []):
        find_text(c, term, current_path)
    for c in node.get('shadowRoot', []):
        find_text(c, term, current_path + " [SHADOW]")

def search():
    with open('shadow_dom_dump.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    for idx, item in enumerate(data):
        print(f"--- Searching in interactive element {idx} ---")
        find_text(item, "turn left")
        find_text(item, "drive forward")

if __name__ == "__main__":
    search()
