# -*- coding: utf-8 -*-
"""
find_koji_coords.py
-------------------
Takes a full screenshot of the Brilliant activity page
using your local Edge profile (logged in).
The screenshot is saved to screenshots/koji_location.png
so we can visually identify where Koji is.
"""

import os
import sys
import subprocess
import time

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

ACTIVITY_URL = (
    "https://brilliant.org/courses/pixel-pusher/intro-to-functions/"
    "pp-returning-values/?from=icp_node&from_llp=computer-science#page-1"
)

SCREENSHOT_PATH = r"D:\internship\myproject\screenshots\koji_location.png"
VIEWPORT_WIDTH  = 1280
VIEWPORT_HEIGHT = 800

def get_edge_user_data_dir():
    return os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\Edge\User Data")

def kill_edge():
    print("[>>] Killing Edge processes...")
    subprocess.run(["taskkill", "/F", "/IM", "msedge.exe"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    print("[OK]  Edge killed.")

def run():
    os.makedirs(os.path.dirname(SCREENSHOT_PATH), exist_ok=True)
    kill_edge()

    with sync_playwright() as p:
        print("[>>] Launching Edge with local profile...")
        context = p.chromium.launch_persistent_context(
            user_data_dir=get_edge_user_data_dir(),
            channel="msedge",
            headless=False,
            viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
            args=["--disable-blink-features=AutomationControlled"],
            no_viewport=False,
        )

        page = context.new_page()
        print("[>>] Navigating to activity...")
        page.goto(ACTIVITY_URL, wait_until="load", timeout=60_000)

        print("[..] Waiting 10s for page to fully render...")
        page.wait_for_timeout(10_000)

        print(f"[i]  Page Title : {page.title()}")

        # Take a viewport screenshot (not full page)
        page.screenshot(path=SCREENSHOT_PATH, full_page=False)
        print(f"\n[OK]  Screenshot saved to:\n      {SCREENSHOT_PATH}")
        print("\nOpen that image to see exactly where Koji is on screen.")

        # Inject live coordinate tracker into the page title
        print("\n[..] Browser stays open 30s -- hover your mouse over Koji.")
        print("     Watch the browser TAB TITLE -- it will show X:... Y:... coordinates!")
        page.evaluate("""
            document.addEventListener('mousemove', function(e) {
                document.title = 'X:' + e.clientX + '  Y:' + e.clientY;
            });
        """)
        page.wait_for_timeout(30_000)

        context.close()
        print("[DONE] Finished.")

if __name__ == "__main__":
    run()
