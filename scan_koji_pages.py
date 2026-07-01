# -*- coding: utf-8 -*-
"""
scan_koji_pages.py
------------------
Scans all free preview URLs and checks which ones actually have
the Koji button (aria-label='chat with tutor').
Saves a screenshot of the first page that HAS Koji.
Outputs a filtered list: koji_pages.txt
"""

import os
import sys
import subprocess
import time

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

# Determine base directory dynamically
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PREVIEW_FILE   = os.path.join(BASE_DIR, "free_previews.txt")
OUTPUT_TXT     = os.path.join(BASE_DIR, "koji_pages.txt")
SCREENSHOT_DIR = os.path.join(BASE_DIR, "screenshots", "koji_scan")
VIEWPORT_WIDTH  = 1280
VIEWPORT_HEIGHT = 800

def get_edge_user_data_dir():
    return os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\Edge\User Data")

def kill_edge():
    subprocess.run(["taskkill", "/F", "/IM", "msedge.exe"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)

def parse_previews(file_path):
    entries = []
    current_course = "Unknown"
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("Course:"):
                current_course = line.replace("Course:", "").strip()
            elif line.startswith("Preview URL:"):
                url = line.replace("Preview URL:", "").strip()
                entries.append({"course": current_course, "url": url})
    return entries

def run():
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    previews = parse_previews(PREVIEW_FILE)
    print(f"Scanning {len(previews)} preview pages for Koji button...\n")

    kill_edge()

    has_koji  = []
    no_koji   = []
    first_koji_screenshot = False

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=get_edge_user_data_dir(),
            channel="msedge",
            headless=False,
            viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
            args=["--disable-blink-features=AutomationControlled"],
            no_viewport=False,
        )
        page = context.new_page()

        for i, entry in enumerate(previews, 1):
            url    = entry["url"]
            course = entry["course"]
            print(f"[{i:02d}/{len(previews)}] {course}")
            print(f"        {url}")

            try:
                page.goto(url, wait_until="load", timeout=60_000)
                page.wait_for_timeout(8_000)

                title = page.title()
                if "Home | Brilliant" in title or "login" in page.url.lower():
                    print(f"        -> LOCKED/REDIRECTED\n")
                    no_koji.append(entry)
                    continue

                # Check for Koji button
                koji = page.locator("[aria-label='chat with tutor']").first
                koji_visible = koji.count() > 0 and koji.is_visible()

                # Also check ALL aria-labels in bottom area to find any variant
                all_aria = page.evaluate("""
                    () => {
                        const els = document.querySelectorAll('[aria-label]');
                        return Array.from(els)
                            .map(e => ({
                                tag: e.tagName,
                                label: e.getAttribute('aria-label'),
                                y: Math.round(e.getBoundingClientRect().y)
                            }))
                            .filter(e => e.y > 600);
                    }
                """)

                bottom_labels = [e['label'] for e in all_aria if e['label']]

                if koji_visible:
                    print(f"        -> [KOJI FOUND!] Bottom labels: {bottom_labels}")
                    has_koji.append(entry)

                    # Take screenshot of first Koji page
                    if not first_koji_screenshot:
                        shot_path = os.path.join(SCREENSHOT_DIR, f"koji_page_{i:02d}.png")
                        page.screenshot(path=shot_path, full_page=False)
                        print(f"        -> Screenshot: {shot_path}")
                        first_koji_screenshot = True
                else:
                    print(f"        -> No Koji. Bottom labels: {bottom_labels}")
                    no_koji.append(entry)

            except Exception as e:
                print(f"        -> ERROR: {e}")
                no_koji.append(entry)

            print()

        context.close()

    # Write results
    with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
        f.write(f"--- PAGES WITH KOJI ({len(has_koji)} found) ---\n\n")
        for e in has_koji:
            f.write(f"Course: {e['course']}\n")
            f.write(f"Preview URL: {e['url']}\n")
            f.write("-" * 40 + "\n")

    print(f"\n{'='*55}")
    print(f"  SCAN COMPLETE")
    print(f"  Pages WITH Koji   : {len(has_koji)}")
    print(f"  Pages WITHOUT Koji: {len(no_koji)}")
    print(f"  Results saved to  : {OUTPUT_TXT}")
    print(f"{'='*55}")

if __name__ == "__main__":
    run()
