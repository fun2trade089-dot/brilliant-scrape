# -*- coding: utf-8 -*-
"""
local_browser_koji.py
---------------------
Opens a Brilliant.org activity using YOUR LOCAL MICROSOFT EDGE PROFILE
(already logged in -- no cookie injection needed), then:
  1. Checks if the login was successful.
  2. Does a blind click on the Koji bot at the bottom-left corner.
  3. Waits so you can see the result.

USAGE:
  python local_browser_koji.py

IMPORTANT:
  Make sure Edge is CLOSED before running this script,
  otherwise Playwright cannot attach to the user data directory.
"""

import os
import sys
import subprocess
import time

# Fix Windows terminal encoding so print() doesn't crash on special chars
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

# ---------------------------------------------------------------
# CONFIG — edit these if needed
# ---------------------------------------------------------------

# The activity URL you want to open
ACTIVITY_URL = (
    "https://brilliant.org/courses/pixel-pusher/intro-to-functions/"
    "pp-returning-values/?from=icp_node&from_llp=computer-science#page-1"
)

# Koji bot selector -- discovered via DOM inspection
# aria-label='chat with tutor' is the reliable way to find it
KOJI_SELECTOR = "[aria-label='chat with tutor']"

# Fallback blind-click coordinates if selector fails
KOJI_X = 112
KOJI_Y = 726

# Viewport must match the size where you verified the coordinates
VIEWPORT_WIDTH  = 1280
VIEWPORT_HEIGHT = 800

# How long (ms) to wait after page load before clicking Koji
SETTLE_MS = 10_000

# How long (ms) to keep browser open after clicking so you can see the result
LINGER_MS = 20_000

# ---------------------------------------------------------------
# Find the local Edge user data directory automatically
# ---------------------------------------------------------------
def get_edge_user_data_dir():
    """Returns the default Microsoft Edge user data path for Windows."""
    return os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        r"Microsoft\Edge\User Data"
    )


def kill_edge():
    """Force-kills all running Edge processes so the profile is free."""
    print("[>>] Killing any running Edge processes...")
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "msedge.exe"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(2)  # Give OS time to fully release the profile lock
        print("[OK]  Edge processes killed. Profile is now free.")
    except Exception as e:
        print(f"[WARN] Could not kill Edge: {e}")


# ---------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------
def run():
    # Use the project-specific profile directory to bypass remote debugging restrictions
    user_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "edge_profile")

    print("=" * 60)
    print("  LOCAL BROWSER (EDGE) + KOJI CLICK")
    print("=" * 60)
    print(f"  Edge profile   : {user_data_dir}")
    print(f"  Activity URL   : {ACTIVITY_URL}")
    print(f"  Koji click at  : ({KOJI_X}, {KOJI_Y})")
    print(f"  Viewport       : {VIEWPORT_WIDTH}x{VIEWPORT_HEIGHT}")
    print("=" * 60)
    print()

    # Auto-kill Edge so the profile lock is released
    kill_edge()
    print()

    # Load session environment variables
    from dotenv import load_dotenv
    load_dotenv()
    session_id = os.getenv("BRILLIANT_SESSION_ID")
    csrf_token = os.getenv("BRILLIANT_CSRF_TOKEN")

    with sync_playwright() as p:
        print("[>>] Launching Microsoft Edge with custom profile...")

        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            channel="msedge",          # use the installed Microsoft Edge
            headless=False,            # must be visible
            slow_mo=300,               # slight slow-mo so actions are visible
            viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
            args=[
                "--disable-blink-features=AutomationControlled",  # avoids bot detection
                "--test-type",
            ],
            no_viewport=False,
        )

        # Inject cookies from .env to log in automatically
        if session_id:
            print("  [i] Injecting Brilliant.org session cookies from .env...")
            context.add_cookies([
                {"name": "sessionid", "value": session_id, "domain": ".brilliant.org", "path": "/"},
                {"name": "csrftoken", "value": csrf_token, "domain": ".brilliant.org", "path": "/"}
            ])

        page = context.new_page()

        # --- Step 1: Navigate ---
        print(f"[>>] Navigating to activity...")
        page.goto(ACTIVITY_URL, wait_until="load", timeout=60_000)

        print(f"[..] Waiting {SETTLE_MS // 1000}s for page to settle...")
        page.wait_for_timeout(SETTLE_MS)

        # --- Step 2: Check login status ---
        current_url = page.url
        page_title  = page.title()
        print(f"\n[i]  Page Title : {page_title}")
        print(f"[i]  Final URL  : {current_url}")

        if "Home | Brilliant" in page_title or "Dashboard" in page_title or "login" in current_url.lower():
            print("\n[FAIL] LOGIN FAILED -- You were redirected to the home/login page.")
            print("   -> Open Chrome manually and log in to brilliant.org first,")
            print("     then close Chrome and run this script again.")
        else:
            print("\n[OK]  LOGIN OK -- You are on the activity page!")

            # --- Step 3: Click Koji via selector (reliable) ---
            print(f"\n[>>] Looking for Koji button with selector: {KOJI_SELECTOR}")
            koji_btn = page.locator(KOJI_SELECTOR).first

            if koji_btn.count() > 0 and koji_btn.is_visible():
                box = koji_btn.bounding_box()
                print(f"[OK]  Found Koji at {box}")
                koji_btn.click()
                print("[OK]  Koji clicked via selector!")
            else:
                # Fallback to coordinates
                print(f"[WARN] Selector not found, falling back to coords ({KOJI_X}, {KOJI_Y})")
                page.mouse.move(KOJI_X, KOJI_Y)
                page.wait_for_timeout(500)
                page.mouse.click(KOJI_X, KOJI_Y)
                print("[OK]  Fallback click done.")

            print("[OK]  Check if Koji chat opened in the browser window!")

        # --- Step 4: Linger ---
        print(f"\n[..] Keeping browser open for {LINGER_MS // 1000}s so you can inspect...")
        page.wait_for_timeout(LINGER_MS)

        context.close()
        print("\n[DONE] Finished.")


if __name__ == "__main__":
    run()
