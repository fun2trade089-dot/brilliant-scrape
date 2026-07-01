# -*- coding: utf-8 -*-
"""
debug_koji_click.py
-------------------
Takes a screenshot BEFORE clicking, tries to find Koji by DOM element,
then takes a screenshot AFTER clicking to see exactly what happened.
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

BEFORE_PATH = r"D:\internship\myproject\screenshots\before_click.png"
AFTER_PATH  = r"D:\internship\myproject\screenshots\after_click.png"
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
    os.makedirs(os.path.dirname(BEFORE_PATH), exist_ok=True)
    kill_edge()

    with sync_playwright() as p:
        print("[>>] Launching Edge...")
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
        print("[..] Waiting 10s for page to render...")
        page.wait_for_timeout(10_000)

        # --- Screenshot BEFORE click ---
        page.screenshot(path=BEFORE_PATH, full_page=False)
        print(f"[OK]  BEFORE screenshot saved: {BEFORE_PATH}")

        # --- Try to find Koji by DOM element ---
        print("\n[>>] Searching for Koji by DOM selectors...")

        # Dump all buttons and clickable elements in the bottom area
        elements_info = page.evaluate("""
            () => {
                const all = document.querySelectorAll('button, [role="button"], [class*="koji"], [class*="Koji"], [class*="chat"], [class*="Chat"], [class*="hint"], [class*="Hint"], [class*="assistant"], [aria-label]');
                return Array.from(all).map(el => {
                    const rect = el.getBoundingClientRect();
                    return {
                        tag: el.tagName,
                        text: el.innerText?.slice(0, 40) || '',
                        ariaLabel: el.getAttribute('aria-label') || '',
                        className: el.className?.slice(0, 60) || '',
                        x: Math.round(rect.x),
                        y: Math.round(rect.y),
                        width: Math.round(rect.width),
                        height: Math.round(rect.height)
                    };
                }).filter(el => el.y > 600);  // Only bottom area elements
            }
        """)

        print(f"\n[i]  Elements found in bottom area (y > 600):")
        for el in elements_info:
            print(f"     [{el['tag']}] aria='{el['ariaLabel']}' class='{el['className'][:40]}' pos=({el['x']},{el['y']}) size={el['width']}x{el['height']} text='{el['text']}'")

        # --- Try clicking by aria-label or class patterns ---
        clicked = False
        selectors_to_try = [
            "[aria-label*='Koji']",
            "[aria-label*='koji']",
            "[aria-label*='hint']",
            "[aria-label*='Hint']",
            "[aria-label*='chat']",
            "[aria-label*='assistant']",
            "[class*='koji']",
            "[class*='Koji']",
            "[class*='KojiButton']",
            "[class*='HintButton']",
        ]

        for sel in selectors_to_try:
            try:
                el = page.locator(sel).first
                if el.count() > 0 and el.is_visible():
                    box = el.bounding_box()
                    print(f"\n[OK]  Found Koji element with selector: {sel}")
                    print(f"      Bounding box: {box}")
                    el.click()
                    clicked = True
                    print(f"[OK]  Clicked via selector!")
                    break
            except:
                pass

        if not clicked:
            print("\n[WARN] Could not find Koji by selector. Trying coordinate click at (65, 725)...")
            page.mouse.click(65, 725)

        # Wait and take AFTER screenshot
        page.wait_for_timeout(3000)
        page.screenshot(path=AFTER_PATH, full_page=False)
        print(f"[OK]  AFTER screenshot saved: {AFTER_PATH}")

        print("\n[..] Keeping browser open 20s for inspection...")
        page.wait_for_timeout(20_000)

        context.close()
        print("[DONE] Finished.")

if __name__ == "__main__":
    run()
