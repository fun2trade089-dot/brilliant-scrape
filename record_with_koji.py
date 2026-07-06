# -*- coding: utf-8 -*-
"""
record_with_koji.py
-------------------
Full pipeline for each Brilliant.org activity:
  1. Kill Edge
  2. Start screen recording (ffmpeg gdigrab) + audio recording (pyaudiowpatch WASAPI loopback) in parallel
  3. Open activity in Edge (with your local logged-in profile)
  4. Click Koji ("chat with tutor" button)
  5. Wait for Koji panel to open
  6. Type a configurable message into Koji chat and send it
  7. Record for the full duration
  8. Stop both recordings, merge video+audio into final MP4

USAGE:
  python record_with_koji.py

REQUIREMENTS:
  - ffmpeg installed (winget install Gyan.FFmpeg)
  - pyaudiowpatch installed (pip install pyaudiowpatch)
  - Microsoft Edge installed and logged in to Brilliant.org
"""

import os
import sys
import re
import time
import wave
import signal
import struct
import subprocess
import threading

from dotenv import load_dotenv
load_dotenv()

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

# ================================================================
# CONFIG  -- edit these as needed
# ================================================================

# Message to type into Koji after it opens
KOJI_MESSAGE = "Can you explain this problem step by step?"

# How many activities to process per run (set to None for all)
MAX_ACTIVITIES = 1

# Start processing from this activity index (1-based, e.g. 2 for second course)
START_ACTIVITY_INDEX = 1

# How many seconds to record each activity after Koji opens
RECORD_SECONDS = 30

# Record until the user closes the browser page/window (max 15 mins)
RECORD_UNTIL_CLOSED = True

# Auto-solve and auto-advance through the activity cards
AUTO_SOLVE = True

import shutil

# Determine base directory dynamically
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Source: koji_pages.txt (pages confirmed to have Koji button)
PREVIEW_FILE = os.path.join(BASE_DIR, "koji_pages.txt")

# Output folder for MP4 recordings
OUTPUT_DIR = os.path.join(BASE_DIR, "recordings", "koji_sessions")

# Temp folder for intermediate video/audio files
TEMP_DIR = os.path.join(OUTPUT_DIR, "_temp")

# Viewport size
VIEWPORT_WIDTH  = 1280
VIEWPORT_HEIGHT = 800

# Wait times (milliseconds)
PAGE_SETTLE_MS  = 3_000   # wait after page load
KOJI_OPEN_WAIT_MS = 3_000  # wait for Koji panel animation

# Full path to ffmpeg (search on system PATH first, then fall back to local path)
FFMPEG_PATH = shutil.which("ffmpeg") or os.environ.get("FFMPEG_PATH") or r"C:\Users\kvsga\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"

# ================================================================
# HELPERS
# ================================================================

def clean_filename(name: str) -> str:
    import re
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def get_edge_user_data_dir():
    return os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\Edge\User Data")

def kill_edge():
    print("  [>>] Killing Edge processes...")
    subprocess.run(["taskkill", "/F", "/IM", "msedge.exe"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    print("  [OK]  Edge killed.")

def check_ffmpeg():
    try:
        r = subprocess.run([FFMPEG_PATH, "-version"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return r.returncode == 0
    except FileNotFoundError:
        return False

def slug_from_url(url: str) -> str:
    clean = url.split("?")[0].rstrip("/").split("/")[-1]
    return re.sub(r"[^a-zA-Z0-9_-]", "_", clean)[:60]

def parse_previews(file_path: str) -> list:
    """
    Parse koji_pages.txt into list of {"course": ..., "url": ...} dicts.
    """
    entries = []
    if not os.path.exists(file_path):
        print(f"[ERROR] File not found: {file_path}")
        return entries

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

# ================================================================
# AUDIO RECORDING (pyaudiowpatch WASAPI loopback)
# ================================================================

class AudioRecorder:
    """Records system audio via WASAPI loopback using pyaudiowpatch."""

    def __init__(self, output_wav_path: str):
        self.output_path = output_wav_path
        self._stop_event = threading.Event()
        self._thread = None
        self._error = None

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._record, daemon=True)
        self._thread.start()
        time.sleep(0.5)  # Give it a moment to initialise

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        if self._error:
            print(f"  [WARN] Audio recording error: {self._error}")

    def _record(self):
        try:
            import pyaudiowpatch as pyaudio
        except ImportError:
            self._error = "pyaudiowpatch not installed. Run: pip install pyaudiowpatch"
            return

        try:
            p = pyaudio.PyAudio()
            # Find WASAPI loopback device
            wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])

            loopback_dev = None
            if default_speakers.get("isLoopbackDevice"):
                loopback_dev = default_speakers
            else:
                for loopback in p.get_loopback_device_info_generator():
                    if default_speakers["name"] in loopback["name"]:
                        loopback_dev = loopback
                        break

            if not loopback_dev:
                self._error = "No WASAPI loopback device found."
                p.terminate()
                return

            channels = loopback_dev["maxInputChannels"]
            rate = int(loopback_dev["defaultSampleRate"])
            chunk = 1024

            stream = p.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=rate,
                input=True,
                input_device_index=loopback_dev["index"],
                frames_per_buffer=chunk,
            )

            # Open wave file upfront for real-time writing
            wf = wave.open(self.output_path, "wb")
            wf.setnchannels(channels)
            wf.setsampwidth(2)  # paInt16 = 2 bytes
            wf.setframerate(rate)

            print(f"  [OK]  Audio recording started (WASAPI loopback, {rate}Hz, {channels}ch)")

            while not self._stop_event.is_set():
                try:
                    data = stream.read(chunk, exception_on_overflow=False)
                    if data:
                        wf.writeframes(data)
                except Exception:
                    break

            stream.stop_stream()
            stream.close()
            p.terminate()
            wf.close()
            print(f"  [OK]  Audio saved: {os.path.basename(self.output_path)}")

        except Exception as e:
            self._error = str(e)

# ================================================================
# VIDEO RECORDING (ffmpeg gdigrab)
# ================================================================

def start_video_recording(output_path: str) -> subprocess.Popen:
    """
    Start ffmpeg with gdigrab (Windows screen capture).
    Video only — audio is handled by AudioRecorder.
    Output is MKV (Matroska) which is crash-resilient — valid even if killed.
    """
    cmd = [
        FFMPEG_PATH, "-y",
        "-f", "gdigrab",
        "-framerate", "15",
        "-i", "desktop",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        output_path
    ]
    print(f"  [>>] Starting video recording -> {os.path.basename(output_path)}")
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
    )
    time.sleep(2)

    # Check if ffmpeg started successfully
    if proc.poll() is not None:
        print(f"  [ERROR] ffmpeg failed to start (exit code: {proc.poll()})")
        return None

    print("  [OK]  Video recording started (gdigrab)")
    return proc

def stop_video_recording(proc: subprocess.Popen):
    """Gracefully stop ffmpeg by sending 'q' to stdin."""
    if proc is None:
        return
    print("  [>>] Stopping video recording...")
    try:
        # Send 'q' to ffmpeg stdin — the standard graceful quit command
        proc.stdin.write(b"q")
        proc.stdin.flush()
        proc.wait(timeout=15)
        print("  [OK]  Video recording stopped gracefully.")
    except Exception as e:
        print(f"  [WARN] Graceful stop failed ({e}), trying CTRL_BREAK...")
        try:
            proc.send_signal(signal.CTRL_BREAK_EVENT)
            proc.wait(timeout=10)
            print("  [OK]  Video recording stopped via CTRL_BREAK.")
        except Exception as e2:
            print(f"  [WARN] CTRL_BREAK also failed ({e2}), force-killing...")
            try:
                proc.kill()
                proc.wait(timeout=5)
            except Exception:
                pass

# ================================================================
# MERGE VIDEO + AUDIO
# ================================================================

def merge_video_audio(video_path: str, audio_path: str, output_path: str) -> bool:
    """Merge video (mp4) and audio (wav) into a single MP4."""
    if not os.path.exists(video_path):
        print(f"  [ERROR] Video file missing: {video_path}")
        return False

    has_audio = os.path.exists(audio_path) and os.path.getsize(audio_path) > 1000

    if has_audio:
        cmd = [
            FFMPEG_PATH, "-y",
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            output_path
        ]
        print("  [>>] Merging video + audio...")
    else:
        # No audio — just copy the video
        print("  [WARN] No audio captured. Saving video only.")
        cmd = [
            FFMPEG_PATH, "-y",
            "-i", video_path,
            "-c:v", "copy",
            output_path
        ]

    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if result.returncode == 0:
        print(f"  [OK]  Merged -> {os.path.basename(output_path)}")
        # Clean up temp files
        try:
            os.remove(video_path)
            if has_audio:
                os.remove(audio_path)
        except Exception:
            pass
        return True
    else:
        stderr = result.stderr.decode(errors="replace")
        print(f"  [ERROR] Merge failed:\n{stderr[:500]}")
        return False

# ================================================================
# PLAYWRIGHT: open page, click Koji, type message
# ================================================================

def setup_koji_on_page(page) -> bool:
    """Clicks Koji button and types the configured message on the current page."""
    page_title = page.title()
    print(f"  [i]  Page title: {page_title}")
    if page_title:
        page.activity_title = page_title.split('|')[0].strip()

    # Check if redirected (locked / not logged in)
    if ("Home | Brilliant" in page_title
            or "Dashboard" in page_title
            or "login" in page.url.lower()):
        print("  [FAIL] Redirected to home/login. Activity is locked.")
        return False

    # Dismiss any modals/overlays
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
        close_selectors = [
            "[aria-label*='close' i]",
            "[class*='close' i]",
            "button:has-text('Dismiss')",
            "button:has-text('Close')",
            "a:has-text('Close')",
            "[aria-label*='dismiss' i]"
        ]
        for sel in close_selectors:
            el = page.locator(sel).first
            if el.count() > 0 and el.is_visible() and el.is_enabled():
                el_aria = el.get_attribute("aria-label") or ""
                if "chat" not in el_aria.lower() and "tutor" not in el_aria.lower():
                    print(f"  [i] Closing overlay element: {sel}")
                    robust_click(page, el)
                    page.wait_for_timeout(500)
    except Exception:
        pass

    # --- Click Koji ---
    print("  [>>] Looking for Koji button [aria-label='chat with tutor']...")
    koji_btn = page.locator("[aria-label='chat with tutor']").first
    try:
        koji_btn.wait_for(state="visible", timeout=10_000)
    except Exception:
        print("  [WARN] Koji button not visible on this page. Skipping.")
        return False

    koji_btn.click()
    print("  [OK]  Koji clicked!")

    # Wait for panel to animate open
    page.wait_for_timeout(KOJI_OPEN_WAIT_MS)

    # --- Type message ---
    print(f"  [>>] Typing message into Koji: '{KOJI_MESSAGE}'")
    typed = False
    chat_selectors = [
        "textarea[placeholder*='help']",
        "input[placeholder*='help']",
        "textarea[placeholder*='message']",
        "input[placeholder*='message']",
        "[class*='chat'] textarea",
        "[class*='chat'] input",
        "textarea",
    ]
    for sel in chat_selectors:
        try:
            el = page.locator(sel).first
            if el.count() > 0 and el.is_visible():
                el.click()
                el.type(KOJI_MESSAGE, delay=50)
                page.wait_for_timeout(500)
                el.press("Enter")
                print(f"  [OK]  Message sent! (selector: {sel})")
                typed = True
                break
        except Exception:
            pass

    if not typed:
        print("  [WARN] Could not find Koji input box. Message not sent.")
    return True

def process_activity(page, url: str) -> bool:
    """Navigate, click Koji, type + send message. Returns True on success."""
    print(f"  [>>] Navigating to: {url}")
    try:
        page.goto(url, wait_until="load", timeout=60_000)
    except Exception as e:
        print(f"  [ERROR] Navigation failed: {e}")
        return False

    print(f"  [..] Waiting {PAGE_SETTLE_MS // 1000}s for page to settle...")
    page.wait_for_timeout(PAGE_SETTLE_MS)

    return setup_koji_on_page(page)

def robust_click(page, locator) -> bool:
    """Scrolls an element into view via JS and attempts normal click, falling back to JS event dispatches and forced click."""
    try:
        if hasattr(locator, "count") and locator.count() == 0:
            return False
        
        el = locator.first if hasattr(locator, "first") else locator
        
        # Scroll to center of the viewport
        try:
            el.evaluate("el => el.scrollIntoView({block: 'center', inline: 'center'})")
            page.wait_for_timeout(300)
        except Exception as scroll_err:
            print(f"    [robust_click] Scroll failed: {scroll_err}")
        
        try:
            el.click(timeout=2000)
            return True
        except Exception as click_err:
            print(f"    [robust_click] Normal click failed ({click_err}), trying JavaScript click/event dispatch fallback...")
            try:
                # Dispatch standard pointer and mouse click events recursively
                el.evaluate("""el => {
                    el.scrollIntoView({block: 'center', inline: 'center'});
                    
                    const opts = { bubbles: true, cancelable: true, view: window };
                    
                    // Dispatch pointer events
                    el.dispatchEvent(new PointerEvent('pointerdown', opts));
                    el.dispatchEvent(new PointerEvent('pointerup', opts));
                    
                    // Dispatch mouse events
                    el.dispatchEvent(new MouseEvent('mousedown', opts));
                    el.dispatchEvent(new MouseEvent('mouseup', opts));
                    el.dispatchEvent(new MouseEvent('click', opts));
                }""")
                return True
            except Exception as js_err:
                print(f"    [robust_click] JavaScript event dispatch failed ({js_err}), trying forced click...")
                try:
                    el.click(force=True, timeout=2000)
                    return True
                except Exception as force_err:
                    print(f"    [robust_click] All click methods failed: {force_err}")
                    return False
    except Exception as e:
        print(f"    [robust_click Exception] {e}")
def robust_drag_and_drop(page, source, target) -> bool:
    """Drags a source element to a target element slowly, simulating realistic mouse movements."""
    try:
        source_el = source.first if hasattr(source, "first") else source
        target_el = target.first if hasattr(target, "first") else target
        
        # 1. Scroll elements into view
        try:
            source_el.scroll_into_view_if_needed()
            target_el.scroll_into_view_if_needed()
            page.wait_for_timeout(100)
        except Exception as scroll_err:
            print(f"    [robust_drag] Scroll failed: {scroll_err}")
        
        # 2. Get bounding boxes
        box_src = source_el.bounding_box()
        box_tgt = target_el.bounding_box()
        
        if not box_src or not box_tgt:
            print("    [robust_drag] Error: Could not get bounding box for source or target.")
            return False
            
        x1 = box_src["x"] + box_src["width"] / 2
        y1 = box_src["y"] + box_src["height"] / 2
        
        x2 = box_tgt["x"] + box_tgt["width"] / 2
        y2 = box_tgt["y"] + box_tgt["height"] / 2
        
        print(f"    [robust_drag] Moving mouse to source center ({x1}, {y1})...")
        page.mouse.move(x1, y1)
        page.wait_for_timeout(50)
        
        print("    [robust_drag] Pressing mouse down...")
        page.mouse.down()
        page.wait_for_timeout(50)
        
        # Move slowly in 8 steps to ensure the drag event registers
        steps = 8
        print(f"    [robust_drag] Dragging to target center ({x2}, {y2}) in {steps} steps...")
        for i in range(1, steps + 1):
            x = x1 + (x2 - x1) * i / steps
            y = y1 + (y2 - y1) * i / steps
            page.mouse.move(x, y)
            page.wait_for_timeout(25) # 25ms pause per step
            
        page.wait_for_timeout(50)
        print("    [robust_drag] Releasing mouse up...")
        page.mouse.up()
        page.wait_for_timeout(200)
        return True
    except Exception as e:
        print(f"    [robust_drag Exception] {e}")
        return False

def ensure_koji_open(page):
    """Checks if the Koji chat tutor panel has closed, and re-opens it if necessary."""
    try:
        # Check if the chat input area is visible
        chat_visible = False
        chat_selectors = [
            "textarea[placeholder*='help']",
            "input[placeholder*='help']",
            "textarea[placeholder*='message']",
            "input[placeholder*='message']",
            "[class*='chat'] textarea",
            "[class*='chat'] input",
        ]
        for sel in chat_selectors:
            el = page.locator(sel).first
            if el.count() > 0 and el.is_visible():
                chat_visible = True
                break
        
        # If chat is not visible, check if Koji button is visible and click it!
        if not chat_visible:
            koji_btn = page.locator("[aria-label='chat with tutor']").first
            if koji_btn.count() > 0 and koji_btn.is_visible() and koji_btn.is_enabled():
                print("  [Koji] Chat panel closed. Re-opening Koji...")
                robust_click(page, koji_btn)
                page.wait_for_timeout(1500)  # Wait for panel to animate open
    except Exception as e:
        print(f"  [Koji Exception] Error checking/re-opening: {e}")

def clear_selections(page) -> bool:
    """Attempts to clear all user inputs (slots, text inputs, checkboxes, etc.) on the current card."""
    print("  [AutoSolve] Clearing card selections...")
    
    # 1. Try to find and click "Start over", "Reset", "Clear"
    reset_btn = page.locator("button, a, [role='button'], [class*='button']").filter(
        has_text=re.compile(r"start over|reset|clear|start again", re.IGNORECASE)
    ).first
    try:
        reset_btn.wait_for(state="visible", timeout=1500)
        if reset_btn.is_enabled():
            print("    [clear_selections] Clicking Start over / Reset button...")
            if robust_click(page, reset_btn):
                # Wait until all slots are actually empty (Elm animation)
                for attempt in range(6):  # Up to 3 seconds (6 x 500ms)
                    page.wait_for_timeout(500)
                    placed = get_placed_blocks_count(page)
                    if placed == 0:
                        break
                return True
    except Exception:
        pass

    # 2. If no reset button, manually clear slots by clicking filled slots
    cleared_any = False
    try:
        slots = page.locator("custom-interactive .dandyDropBeacon, custom-interactive [aria-description='Slot'], custom-interactive [id*='slot_line_']").all()
        for s in slots:
            if s.is_visible():
                el_id = s.get_attribute("id") or ""
                el_desc = s.get_attribute("aria-description") or ""
                if "bank" not in el_id.lower() and "bank" not in el_desc.lower():
                    slot_text = (s.text_content() or "").strip()
                    if slot_text:
                        print(f"    [clear_selections] Clicking filled slot to eject block: {el_id} ({slot_text})")
                        # Find actual inner elements that can intercept the click and click them directly
                        child_block = s.locator("span, div, [class*='draggable'], [class*='block']").first
                        if child_block.count() > 0 and child_block.is_visible():
                            try:
                                child_block.click(force=True, timeout=500)
                            except Exception:
                                robust_click(page, child_block)
                        else:
                            try:
                                s.click(force=True, timeout=500)
                            except Exception:
                                robust_click(page, s)
                        page.wait_for_timeout(500)
                        cleared_any = True
    except Exception as e:
        print(f"    [clear_selections] Error clearing slots: {e}")

    # 3. Manually deselect checked checkboxes/options
    try:
        choices = page.locator("custom-interactive label, [role='radio'], [role='checkbox'], button[role='checkbox'], button[role='radio']").all()
        if not choices:
            choices = page.locator("[class*='choice'], [class*='option']").all()
        for c in choices:
            if c.is_visible():
                is_checked = c.evaluate("""el => {
                    return el.getAttribute('aria-checked') === 'true' || 
                           el.classList.contains('selected') || 
                           el.classList.contains('checked') || 
                           el.classList.contains('active') ||
                           (el.querySelector('[aria-checked="true"]') !== null) ||
                           (el.closest('[class*="selected"], [class*="checked"]') !== null);
                }""")
                if is_checked:
                    c_text = c.get_attribute("data-scene-graph-name") or c.get_attribute("aria-label") or c.inner_text().strip().replace('\n', ' ')
                    print(f"    [clear_selections] Deselecting option: {c_text}")
                    robust_click(page, c)
                    page.wait_for_timeout(200)
                    cleared_any = True
    except Exception as e:
        print(f"    [clear_selections] Error deselecting choices: {e}")

    if cleared_any:
        page.wait_for_timeout(500)
        return True
        
    return False

def count_slots_static(page) -> int:
    """Finds the number of programming slots inside custom-interactive by counting dandyDropBeacons or Slot elements, excluding choices bank."""
    try:
        # Pierce shadow DOM to find slot elements by class, aria-description, or ID pattern
        slots = page.locator("custom-interactive .dandyDropBeacon, custom-interactive [aria-description='Slot'], custom-interactive [id*='slot_line_']").all()
        visible_slots = []
        for s in slots:
            if s.is_visible():
                el_id = s.get_attribute("id") or ""
                el_desc = s.get_attribute("aria-description") or ""
                # Exclude choice bank slots
                if "bank" not in el_id.lower() and "bank" not in el_desc.lower():
                    visible_slots.append(s)
        if visible_slots:
            return len(visible_slots)
    except Exception as e:
        print(f"  [count_slots_static Exception] {e}")
    return 0

def get_placed_blocks_count(page) -> int:
    """Counts the number of successfully placed blocks in the code editor slots.
    
    After a block is dragged into a slot, the Elm framework re-renders it as
    plain <span> elements with text (e.g. 'turn left'), NOT as draggable elements.
    So we detect filled slots by checking if the slot has non-empty text_content.
    NOTE: inner_text() returns '' because Brilliant hides text via CSS.
    text_content() returns raw DOM text regardless of CSS visibility.
    """
    try:
        slots = page.locator("custom-interactive .dandyDropBeacon, custom-interactive [aria-description='Slot'], custom-interactive [id*='slot_line_']").all()
        count = 0
        for s in slots:
            if s.is_visible():
                el_id = s.get_attribute("id") or ""
                el_desc = s.get_attribute("aria-description") or ""
                if "bank" not in el_id.lower() and "bank" not in el_desc.lower():
                    # A filled slot has non-empty text content (e.g. "turnleft")
                    # An empty slot has no text content
                    slot_text = (s.text_content() or "").strip()
                    if slot_text:
                        count += 1
        return count
    except Exception as e:
        print(f"  [get_placed_blocks_count Exception] {e}")
        return 0

def get_puzzle_requirements(page) -> int:
    """
    Determines the number of answers/selections required for the current card.
    Uses multiple fallback heuristics including:
    1. Checkbox vs Radio button detection.
    2. Instruction text parsing (e.g., "Select 2", "Choose all that apply").
    3. Blank markers inside question text (e.g., "___").
    4. Input and Select fields counting.
    5. Custom data attributes or tag classes.
    6. SVG programming slots visual coordinate analysis.
    """
    print("  [AutoSolve] Evaluating puzzle requirements...")
    
    # 1. HTML structure / data attributes (e.g., data-answers-required, data-type)
    try:
        interactive = page.locator("custom-interactive").first
        if interactive.count() > 0:
            req_attr = interactive.get_attribute("data-answers-required") or interactive.get_attribute("answers-required")
            if req_attr and req_attr.isdigit():
                val = int(req_attr)
                print(f"    [Heuristic] Found answers-required attribute: {val}")
                return val
    except:
        pass

    # 2. Checkbox vs Radio button detection
    try:
        radios = page.locator("input[type='radio'], [role='radio']").all()
        visible_radios = [r for r in radios if r.is_visible()]
        if visible_radios:
            print("    [Heuristic] Radio buttons detected. Single answer required (1).")
            return 1
            
        checkboxes = page.locator("input[type='checkbox'], [role='checkbox']").all()
        visible_checkboxes = [c for c in checkboxes if c.is_visible()]
        if visible_checkboxes:
            print(f"    [Heuristic] Checkboxes detected ({len(visible_checkboxes)}). Multi-answer card.")
    except:
        pass

    # 3. Explicit instruction text parsing using regex/keyword matching
    try:
        # Get card content/header texts
        text_content = page.locator("body").inner_text()
        
        # Matches patterns like "Select 2 options", "Choose 3 blocks", "Select both", "Select all 3", "Choose 2"
        match_num = re.search(r"\b(select|choose|pick)\b\s+(all\s+)?(\d+|both|two|three|four)\b", text_content, re.IGNORECASE)
        if match_num:
            num_str = match_num.group(3).lower()
            word_map = {"both": 2, "two": 2, "three": 3, "four": 4}
            val = word_map.get(num_str, int(num_str) if num_str.isdigit() else None)
            if val is not None:
                print(f"    [Heuristic] Parsed instruction text for count: {val}")
                return val
                
        # Matches "Choose all that apply" -> try everything
        if re.search(r"choose all that apply|select all correct|select all that apply", text_content, re.IGNORECASE):
            print("    [Heuristic] Instruction specifies 'choose all that apply'. Will test all combinations.")
    except:
        pass

    # 4. Blank markers inside the question text itself (e.g. "___")
    try:
        question_text = page.locator("custom-interactive, [class*='question'], [class*='instruction']").first.inner_text(timeout=1000)
        # Count blank sequences like three or more underscores: "___"
        blank_matches = re.findall(r"_{3,}|\[blank\]|__\s*__", question_text, re.IGNORECASE)
        if blank_matches:
            val = len(blank_matches)
            print(f"    [Heuristic] Counted {val} blanks/underscores in question text.")
            return val
    except:
        pass

    # 5. Count empty/blank input and select fields (for fill-in-the-blank style puzzles)
    try:
        inputs = page.locator("input[type='text'], input[type='number'], select").all()
        visible_inputs = [i for i in inputs if i.is_visible() and i.is_enabled()]
        if visible_inputs:
            val = len(visible_inputs)
            print(f"    [Heuristic] Found {val} visible input/select fields.")
            return val
    except:
        pass

    # 6. SVG Slots and Blocks Visual Coordinate Analysis
    try:
        # Check if custom-interactive SVG is present
        card = page.locator("custom-interactive").first
        if card.count() > 0:
            svg_data = card.evaluate("""el => {
                if (!el.shadowRoot) return null;
                const svg = el.shadowRoot.querySelector('svg');
                if (!svg) return null;
                
                const rects = svg.querySelectorAll('rect');
                const svgRect = svg.getBoundingClientRect();
                
                let slotCount = 0;
                rects.forEach(r => {
                    const rect = r.getBoundingClientRect();
                    const relativeX = rect.left - svgRect.left;
                    if (relativeX < 200 && rect.width > 50 && rect.height > 20) {
                        slotCount++;
                    }
                });
                return { isSlot: rects.length > 0, count: slotCount };
            }""")
            if svg_data and svg_data['isSlot']:
                val = svg_data['count']
                if val > 0:
                    print(f"    [Heuristic] Counted {val} SVG slot placeholders on the left.")
                    return val
    except Exception as e:
        pass

    # Default fallback: assume 1 answer
    print("    [Heuristic] Defaulting to 1 answer.")
    return 1

def auto_solve_card(page) -> bool:
    """Attempts to auto-solve or advance the current card. Returns True if action taken."""
    try:
        # Keep Koji panel open throughout the activity
        ensure_koji_open(page)
        # Initialize sequence tracking variables if they don't exist yet on page
        if not hasattr(page, "failed_sequences"):
            page.failed_sequences = []
        if not hasattr(page, "current_sequence"):
            page.current_sequence = []
        if not hasattr(page, "slots_count"):
            page.slots_count = None
            
        # Count slots to see if this is a slot-based card
        slots_count_static = count_slots_static(page)
        is_slot_card = slots_count_static > 0

        # If we don't know the slots count yet, evaluate it
        if page.slots_count is None:
            if is_slot_card:
                page.slots_count = slots_count_static
            else:
                # Use static heuristics for standard questions
                page.slots_count = get_puzzle_requirements(page)
                
        slots_count = page.slots_count
        order_matters = slots_count > 1

        # 1. Try to click "Continue" or "Next" (standard way to advance)
        continue_btns = page.locator("button, a, [role='button']").all()
        visible_continues = []
        for b in continue_btns:
            try:
                if b.is_visible() and b.is_enabled():
                    text = ' '.join((b.text_content() or "").strip().lower().split())
                    if text in ["continue", "next", "proceed", "advance", "next card"] or text.startswith("continue to next"):
                        visible_continues.append(b)
            except Exception:
                pass
        if visible_continues:
            print(f"  [AutoSolve] Clicking Continue ({len(visible_continues)} visible found)...")
            if robust_click(page, visible_continues[0]):
                # Successfully progressed, reset failed and current sequence trackings
                page.failed_sequences = []
                page.current_sequence = []
                page.slots_count = None
                print("  [AutoSolve] Settle wait for the next card...")
                page.wait_for_timeout(1500)
                return True

        # 1.5. Try to click "Try again" or "Start over" if incorrect
        # Clicking this resets the card and enables the remaining choice options
        try_again_btns = page.locator("button, a, [role='button'], [class*='button']").filter(
            has_text=re.compile(r"try again|try another|try once more|retry|give it another shot|give it a shot", re.IGNORECASE)
        ).all()
        visible_try_agains = [b for b in try_again_btns if b.is_visible() and b.is_enabled()]
        
        start_over_btns = page.locator("button, a, [role='button'], [class*='button']").filter(
            has_text=re.compile(r"start over|reset|clear|start again", re.IGNORECASE)
        ).all()
        
        if visible_try_agains:
            clicked = False
            
            # 1. Click Try Again first
            print(f"  [AutoSolve] Clicking Try Again...")
            clicked = robust_click(page, visible_try_agains[0])
            page.wait_for_timeout(500)
                
            # 2. Click Start Over to ensure selections/slots are fully cleared
            visible_start_overs = [b for b in start_over_btns if b.is_visible() and b.is_enabled()]
            if visible_start_overs:
                print(f"  [AutoSolve] Clicking Start over...")
                clicked = robust_click(page, visible_start_overs[0]) or clicked
                page.wait_for_timeout(500)
                
            if clicked:
                # Add current sequence to failed sequences
                if page.current_sequence:
                    print(f"  [AutoSolve] Attempt failed: {page.current_sequence}. Adding to failed sequences.")
                    if page.current_sequence not in page.failed_sequences:
                        page.failed_sequences.append(page.current_sequence)
                page.current_sequence = []
                page.wait_for_timeout(500)
                
                # Clear selections just in case anything is still selected
                clear_selections(page)
                page.wait_for_timeout(500)
                return True

        # 2. Try to click "Show explanation" or "Show answer" or "Explain" or "Give up" or "Solve" or "Show me"
        # If we got the question wrong or are stuck, showing the explanation will let us progress.
        explain_btns = page.locator("button, a, [role='button']").filter(
            has_text=re.compile(r"explanation|explain|answer|give up|solve|show me", re.IGNORECASE)
        ).all()
        visible_explains = [b for b in explain_btns if b.is_visible() and b.is_enabled()]
        if visible_explains:
            print(f"  [AutoSolve] Clicking Show Explanation ({len(visible_explains)} visible found)...")
            if robust_click(page, visible_explains[0]):
                page.failed_sequences = []
                page.current_sequence = []
                page.slots_count = None
                return True

        # 3. Try to click a choice option
        if is_slot_card:
            choices = page.locator("custom-interactive [id*='slot_bank_'] .android-draggable, custom-interactive [id*='slot_bank_'] [dandy-draggable='true']").all()
        else:
            choices = page.locator("custom-interactive label, [role='radio'], [role='checkbox'], button[role='checkbox'], button[role='radio']").all()
            if not choices:
                choices = page.locator("[class*='choice'], [class*='option']").all()
                
        visible_choices = [c for c in choices if c.is_visible()]
        if visible_choices:
            # We want to check if the check button is already enabled. If it is enabled, we don't need to select a choice again.
            check_btns = page.locator("button, a, [role='button']").filter(
                has_text=re.compile(r"^(Check|Submit|Check Answer|Submit Answer|Submit response)$", re.IGNORECASE)
            ).all()
            check_enabled = False
            for b in check_btns:
                if b.is_visible() and b.is_enabled():
                    class_attr = b.get_attribute("class") or ""
                    aria_disabled = b.get_attribute("aria-disabled") or ""
                    if "disabled" not in class_attr.lower() and "pointer-events-none" not in class_attr.lower() and aria_disabled.lower() != "true":
                        check_enabled = True
                        break
            
            # Determine if we are ready to check
            if is_slot_card:
                ready_to_check = len(page.current_sequence) >= slots_count
            else:
                ready_to_check = check_enabled
            
            # Filter out choices that are incorrect, disabled, or already correct
            valid_choices = []
            for c in visible_choices:
                try:
                    aria_desc = c.get_attribute("aria-description") or ""
                    aria_disabled = c.get_attribute("aria-disabled") or ""
                    class_attr = c.get_attribute("class") or ""
                    disabled_attr = c.get_attribute("disabled") is not None
                    
                    is_invalid = (
                        "disabled" in aria_desc.lower() or 
                        "incorrect" in aria_desc.lower() or 
                        "wrong" in aria_desc.lower() or
                        "correct" in aria_desc.lower() or
                        aria_disabled.lower() == "true" or 
                        disabled_attr or
                        "disabled" in class_attr.lower() or
                        "incorrect" in class_attr.lower()
                    )
                    
                    if not is_invalid:
                        valid_choices.append(c)
                    else:
                        c_name = c.get_attribute("data-scene-graph-name") or c.get_attribute("aria-label") or "option"
                        print(f"  [AutoSolve] Skipping disabled/incorrect/correct option '{c_name}' (aria-description: '{aria_desc}', class: '{class_attr}')")
                except Exception:
                    valid_choices.append(c)

            if not ready_to_check and valid_choices:
                # 1. Gather all valid choice elements and their text
                valid_choice_data = []
                for c in valid_choices:
                    try:
                        is_in_slot = c.evaluate("""el => {
                            let parent = el.parentElement;
                            while (parent) {
                                if (parent.id && parent.id.includes('slot_line')) {
                                    return true;
                                }
                                parent = parent.parentElement;
                            }
                            return false;
                        }""")
                    except Exception:
                        is_in_slot = False
                    
                    if not is_in_slot:
                        # Extract clean text/label to unify duplicate commands (prevent repeating identical permutations)
                        try:
                            raw_text = c.evaluate("""el => {
                                const clone = el.cloneNode(true);
                                clone.querySelectorAll('style, script').forEach(s => s.remove());
                                return clone.textContent || '';
                            }""").strip().lower().replace('\n', ' ')
                            raw_text = ' '.join(raw_text.split())
                        except Exception:
                            raw_text = (c.text_content() or "").strip().lower().replace('\n', ' ')
                            raw_text = ' '.join(raw_text.split())
                        if not raw_text:
                            raw_text = (c.get_attribute("aria-label") or "").strip().lower()
                        if not raw_text:
                            raw_text = (c.get_attribute("data-scene-graph-name") or "").strip().lower()
                        c_text = raw_text if raw_text else "option"
                        valid_choice_data.append((c, c_text))

                # Safeguard: if we are starting a new sequence (current_sequence is empty),
                # manually clear/deselect any currently checked/selected options first!
                if not page.current_sequence and valid_choice_data:
                    deselected_any = False
                    for c, c_text in valid_choice_data:
                        try:
                            is_checked = c.evaluate("""el => {
                                return el.getAttribute('aria-checked') === 'true' || 
                                       el.classList.contains('selected') || 
                                       el.classList.contains('checked') || 
                                       el.classList.contains('active') ||
                                       (el.querySelector('[aria-checked="true"]') !== null) ||
                                       (el.closest('[class*="selected"], [class*="checked"]') !== null);
                            }""")
                            if is_checked:
                                print(f"  [AutoSolve] Deselecting already checked option: {c_text}")
                                robust_click(page, c)
                                page.wait_for_timeout(300)
                                deselected_any = True
                        except Exception as e:
                            pass
                    if deselected_any:
                        page.wait_for_timeout(500)
                        return True

                # 2. Determine if order matters and if we have slots (pre-computed at card level)
                # If we are already at the maximum length (slots count), we shouldn't select any more choices!
                if is_slot_card and len(page.current_sequence) >= slots_count:
                    print(f"  [AutoSolve] Slots filled ({len(page.current_sequence)}/{slots_count}). Waiting to Check/Submit...")
                    return False

                # 3. Filter valid choices to systematically try combinations
                filtered_choices = []
                for c, c_text in valid_choice_data:
                    # Skip if already selected in the current sequence ONLY IF it's NOT a slot-based card
                    if not is_slot_card and c_text in page.current_sequence:
                        continue
                        
                    potential_seq = page.current_sequence + [c_text]
                    
                    is_failed = False
                    for f_seq in page.failed_sequences:
                        if order_matters:
                            if potential_seq == f_seq:
                                is_failed = True
                                break
                        else:
                            if set(potential_seq) == set(f_seq) and len(potential_seq) == len(f_seq):
                                is_failed = True
                                break
                                
                    if not is_failed:
                        filtered_choices.append((c, c_text))
                    else:
                        print(f"  [AutoSolve] Rejecting option '{c_text}' as combination {potential_seq} already failed.")
                
                # 4. If no valid options are left from the current sequence, backtrack
                if not filtered_choices:
                    print(f"  [AutoSolve] All options from {page.current_sequence} lead to failed combinations.")
                    if page.current_sequence:
                        if page.current_sequence not in page.failed_sequences:
                            page.failed_sequences.append(page.current_sequence)
                        clear_selections(page)
                        page.current_sequence = []
                        return True
                    else:
                        # No valid options remain — skip this card
                        print(f"  [AutoSolve] No valid options remain ({len(page.failed_sequences)} combos tried). Falling back to Show Explanation.")
                        explain_btns = page.locator("button, a, [role='button']").filter(
                            has_text=re.compile(r"explanation|explain|answer|give up|solve|show me|get help", re.IGNORECASE)
                        ).all()
                        visible_explains = [b for b in explain_btns if b.is_visible() and b.is_enabled()]
                        if visible_explains:
                            print(f"  [AutoSolve] Clicking Show Explanation to skip...")
                            if robust_click(page, visible_explains[0]):
                                page.failed_sequences = []
                                page.current_sequence = []
                                return True
                        
                        print("  [AutoSolve] No explanation button found. Clearing failed_sequences and retrying...")
                        page.failed_sequences = []
                        return True
                
                # 5. Systematically select the next valid choice (lexicographical order)
                page.wait_for_timeout(200)  # Let layout animations settle
                filtered_choices.sort(key=lambda x: x[1])
                chosen_choice, chosen_text = filtered_choices[0]
                
                print(f"  [AutoSolve] Selecting choice '{chosen_text}' for sequence {page.current_sequence + [chosen_text]}")
                
                before_count = get_placed_blocks_count(page)
                
                if is_slot_card:
                    # Find the first empty slot to drag the choice block into
                    slots = page.locator("custom-interactive .dandyDropBeacon, custom-interactive [aria-description='Slot'], custom-interactive [id*='slot_line_']").all()
                    first_empty_slot = None
                    for s in slots:
                        if s.is_visible():
                            el_id = s.get_attribute("id") or ""
                            el_desc = s.get_attribute("aria-description") or ""
                            if "bank" not in el_id.lower() and "bank" not in el_desc.lower():
                                # Empty slot has no text_content; filled slot has text like "turnleft"
                                slot_text = (s.text_content() or "").strip()
                                if not slot_text:
                                    first_empty_slot = s
                                    break
                    
                    if first_empty_slot:
                        try:
                            print(f"    [AutoSolve] Dragging choice '{chosen_text}' to slot: {first_empty_slot.get_attribute('id')}")
                            # Restore slower robust drag-and-drop to ensure event listeners register it
                            robust_drag_and_drop(page, chosen_choice, first_empty_slot)
                            page.wait_for_timeout(800)  # Wait for Elm to re-render
                        except Exception as drag_err:
                            print(f"    [AutoSolve] Drag failed: {drag_err}. Falling back to click.")
                            robust_click(page, chosen_choice)
                            page.wait_for_timeout(300)
                    else:
                        print("    [AutoSolve] Warning: No empty slot found to drag block into.")
                        robust_click(page, chosen_choice)
                        page.wait_for_timeout(300)
                else:
                    # Standard multiple choice/checkbox card - click
                    robust_click(page, chosen_choice)
                    page.wait_for_timeout(300)
                    
                after_count = get_placed_blocks_count(page)
                
                # Brief debug: log placed count
                if is_slot_card:
                    print(f"    [debug] Placed blocks: {before_count} -> {after_count}")
                
                if not is_slot_card or after_count > before_count:
                    # Success! Block was placed (or not a slot card)
                    page.current_sequence.append(chosen_text)
                    return True
                else:
                    # Drag or click did not fill a slot (rejected or limit reached)
                    bad_seq = page.current_sequence + [chosen_text]
                    print(f"  [AutoSolve] Choice '{chosen_text}' did not fill a slot (placed count stayed at {before_count}). Rejecting sequence: {bad_seq}")
                    if bad_seq not in page.failed_sequences:
                        page.failed_sequences.append(bad_seq)
                    
                    # Reset the board to clear any partial state
                    clear_selections(page)
                    page.current_sequence = []
                    return True

        # 4. Check for text or numeric inputs
        inputs = page.locator("custom-interactive input, input[type='text'], input[type='number'], input:not([type])").all()
        visible_inputs = [i for i in inputs if i.is_visible() and i.is_enabled()]
        action_taken = False
        for inp in visible_inputs:
            # Only type if empty
            val = inp.input_value()
            if not val:
                print("  [AutoSolve] Filling text/number input...")
                if robust_click(page, inp):
                    inp.fill("1") # generic default guess
                    page.wait_for_timeout(500)
                    action_taken = True
        if action_taken:
            return True

        # 5. Try to click "Check" or "Submit" (only if enabled and ready!)
        if not is_slot_card or len(page.current_sequence) >= slots_count:
            check_btns = page.locator("button, a, [role='button']").all()
            visible_checks = []
            for b in check_btns:
                try:
                    if b.is_visible() and b.is_enabled():
                        text = ' '.join((b.text_content() or "").strip().lower().split())
                        if text in ["check", "submit", "check answer", "submit answer", "submit response"]:
                            class_attr = b.get_attribute("class") or ""
                            aria_disabled = b.get_attribute("aria-disabled") or ""
                            if "disabled" not in class_attr.lower() and "pointer-events-none" not in class_attr.lower() and aria_disabled.lower() != "true":
                                visible_checks.append(b)
                except Exception:
                    pass
            if visible_checks:
                # Safeguard: if current_sequence is empty, we shouldn't submit the previous incorrect answer again!
                if not hasattr(page, "current_sequence") or not page.current_sequence:
                    print("  [AutoSolve] Check is enabled but current_sequence is empty. Forcing reset/deselect...")
                    clear_selections(page)
                    return True
                    
                print(f"  [AutoSolve] Clicking Check/Submit ({len(visible_checks)} visible found)...")
                if robust_click(page, visible_checks[0]):
                    return True

    except Exception as e:
        print(f"  [AutoSolve Exception] {e}")

    return False

# ================================================================
# MAIN
# ================================================================

def main():
    print("=" * 65)
    print("  BRILLIANT ACTIVITY RECORDER WITH KOJI")
    print("=" * 65)

    # 1. Check ffmpeg
    if not check_ffmpeg():
        print(f"\n[ERROR] ffmpeg not found at:\n  {FFMPEG_PATH}")
        print("  Run: winget install Gyan.FFmpeg")
        print("  Then update FFMPEG_PATH in this script if needed.")
        return
    print("[OK]  ffmpeg found.")

    # 2. Check pyaudiowpatch
    try:
        import pyaudiowpatch
        print("[OK]  pyaudiowpatch found.")
    except ImportError:
        print("[WARN] pyaudiowpatch not found. Audio will NOT be recorded.")
        print("  Run: pip install pyaudiowpatch")

    # 3. Read preview URLs
    print(f"\n[>>] Reading previews from: {PREVIEW_FILE}")
    previews = parse_previews(PREVIEW_FILE)
    if not previews:
        print("[ERROR] No preview URLs found. Run scan_koji_pages.py first.")
        return

    to_process = previews
    print(f"[OK]  Found {len(previews)} previews.\n")

    # 4. Create output directories
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)

    # 5. Kill Edge upfront
    kill_edge()

    # 6. Launch Edge once, reuse across all activities
    with sync_playwright() as p:
        print("\n[>>] Launching Edge with custom profile...")
        
        # Use a dedicated profile directory in the project folder to prevent lock conflicts 
        # and bypass security restrictions on default browser profile directories.
        playwright_profile_dir = os.path.join(BASE_DIR, "edge_profile")
        
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=playwright_profile_dir,
                channel="msedge",
                headless=False,
                viewport={"width": 1280, "height": 800},
                args=["--disable-blink-features=AutomationControlled"],
                no_viewport=False,
            )
        except Exception as launch_err:
            print(f"\n[ERROR] Failed to launch Edge browser context: {launch_err}")
            print("Please check that Edge is not currently locked or in a bad state.")
            return
        
        # Inject Brilliant.org session cookies from .env to log in automatically
        session_id = os.getenv("BRILLIANT_SESSION_ID")
        csrf_token = os.getenv("BRILLIANT_CSRF_TOKEN")
        if session_id:
            print("  [i] Injecting Brilliant.org session cookies from .env...")
            context.add_cookies([
                {"name": "sessionid", "value": session_id, "domain": ".brilliant.org", "path": "/"},
                {"name": "csrftoken", "value": csrf_token, "domain": ".brilliant.org", "path": "/"}
            ])
            
        page = context.new_page()
        print("[OK]  Edge launched.\n")

        success_count = 0
        fail_count    = 0

        for i, entry in enumerate(to_process, 1):
            if START_ACTIVITY_INDEX and i < START_ACTIVITY_INDEX:
                print(f"  [SKIP] Skipping activity {i}/{len(to_process)} (start index is {START_ACTIVITY_INDEX})")
                continue
            if MAX_ACTIVITIES and i >= START_ACTIVITY_INDEX + MAX_ACTIVITIES:
                print(f"  [STOP] Reached limit of MAX_ACTIVITIES ({MAX_ACTIVITIES})")
                break

            course = entry["course"]
            url    = entry["url"]
            slug   = slug_from_url(url)
            # 1. Navigate first to get the browser/activity title
            print(f"\n{'=' * 65}")
            print(f"  [{i}/{len(to_process)}] {course}")
            print(f"  URL    : {url}")
            print(f"{'=' * 65}")

            try:
                page.goto(url, wait_until="load", timeout=60_000)
            except Exception as e:
                print(f"  [ERROR] Navigation failed: {e}")
                fail_count += 1
                continue

            print(f"  [..] Waiting {PAGE_SETTLE_MS // 1000}s for page to settle...")
            page.wait_for_timeout(PAGE_SETTLE_MS)

            # Extract dynamic activity title from browser title
            page_title = page.title() or ""
            act_title = page_title.split('|')[0].strip() if page_title else slug
            act_name_clean = clean_filename(act_title)

            # Set up output directory using the activity name from the start!
            activity_dir = os.path.join(OUTPUT_DIR, act_name_clean)
            os.makedirs(activity_dir, exist_ok=True)
            final_out = os.path.join(activity_dir, f"{act_name_clean}.mp4")

            # Check if this activity is already recorded
            if os.path.exists(final_out) and os.path.getsize(final_out) > 50_000:
                print("  [SKIP] Already recorded.")
                continue

            # Temp files for video and audio
            temp_video = os.path.join(TEMP_DIR, f"{i:03d}_{slug}_video.mkv")
            temp_audio = os.path.join(TEMP_DIR, f"{i:03d}_{slug}_audio.wav")

            # Start BOTH recordings in parallel after dynamic folder setup!
            audio_rec = AudioRecorder(temp_audio)
            audio_rec.start()
            video_proc = start_video_recording(temp_video)

            # Now open Koji and click/setup
            success = setup_koji_on_page(page)

            if success:
                if AUTO_SOLVE:
                    print("  [..] Auto-Solving and Recording full activity...")
                    print("  [..] The script will automatically solve and advance until the activity is completed.")
                    start_url = page.url
                    no_action_count = 0
                    max_wait_seconds = 600  # 10 minutes maximum solve time
                    start_time = time.time()
                    
                    # Reset sequence variables for each new activity!
                    page.failed_sequences = []
                    page.current_sequence = []
                    
                    current_lesson_url_base = start_url.split('#')[0].split('?')[0]
                    
                    try:
                        while not page.is_closed() and (time.time() - start_time < max_wait_seconds):
                            # Clean page URL check (ignore hash/anchor parameters)
                            current_url_base = page.url.split('#')[0].split('?')[0]
                            start_url_base = start_url.split('#')[0].split('?')[0]
                            
                            # Check if the URL changed from the initial activity URL (completed!)
                            if current_url_base != start_url_base:
                                print(f"  [AutoSolve] URL changed from {start_url_base} to {current_url_base}. Activity completed.")
                                break
                            
                            # Check if the page is on a Skill Check or Skill Test card
                            is_skill_check = False
                            for indicator in ["Skill Check", "Skill Test", "Review Quiz", "Checkpoint"]:
                                try:
                                    indicator_el = page.get_by_text(indicator, exact=False).first
                                    if indicator_el.count() > 0 and indicator_el.is_visible():
                                        is_skill_check = True
                                        print(f"  [AutoSolve] Detected '{indicator}'. Stopping activity as requested.")
                                        break
                                except Exception:
                                    pass
                            if is_skill_check:
                                break
                                
                            # Safety: if too many failed combos, force-skip via explanation
                            if hasattr(page, 'failed_sequences') and len(page.failed_sequences) >= 15:
                                print(f"  [AutoSolve] Hit 15 failed combinations. Force-skipping card...")
                                explain_btns = page.locator("button, a, [role='button']").filter(
                                    has_text=re.compile(r"explanation|explain|answer|give up|solve|show me|get help", re.IGNORECASE)
                                ).all()
                                visible_explains = [b for b in explain_btns if b.is_visible() and b.is_enabled()]
                                if visible_explains:
                                    robust_click(page, visible_explains[0])
                                    page.failed_sequences = []
                                    page.current_sequence = []
                                    page.wait_for_timeout(1500)
                                    continue
                                else:
                                    # No explanation button, just reset and keep trying
                                    page.failed_sequences = []
                            
                            action_taken = auto_solve_card(page)
                            if action_taken:
                                no_action_count = 0
                                page.wait_for_timeout(1000)  # Wait for animation
                            else:
                                no_action_count += 1
                                if no_action_count > 15:  # 15 seconds with no interactable buttons
                                    print("  [AutoSolve] No actionable elements found for 15 seconds. Assuming done.")
                                    break
                                page.wait_for_timeout(1000)
                    except Exception as e:
                        print(f"  [AutoSolve Exception] Error in solve loop: {e}")
                elif RECORD_UNTIL_CLOSED:
                    print("  [..] Recording full activity. Solve/click through the activity in the browser...")
                    print("  [..] Once you finish the activity, close the browser window to stop and save the recording.")
                    try:
                        # Wait for close event with 15-minute timeout (900,000 milliseconds)
                        page.wait_for_event("close", timeout=900_000)
                        print("  [OK] Browser tab/window closed. Finalizing recording...")
                    except Exception:
                        print("  [WARN] Recording finished (timeout or window closed).")
                else:
                    print(f"  [..] Recording interaction for {RECORD_SECONDS}s...")
                    time.sleep(RECORD_SECONDS)
                success_count += 1
            else:
                fail_count += 1
                time.sleep(3)

            # Stop BOTH recordings
            audio_rec.stop()
            stop_video_recording(video_proc)

            # Merge video + audio into final MP4
            if video_proc is not None:
                merge_video_audio(temp_video, temp_audio, final_out)
            else:
                print("  [ERROR] No video was recorded for this activity.")

            time.sleep(2)   # small gap between activities

        context.close()

    # Clean up temp directory
    try:
        if os.path.isdir(TEMP_DIR) and not os.listdir(TEMP_DIR):
            os.rmdir(TEMP_DIR)
    except Exception:
        pass

    # Summary
    print(f"\n{'=' * 65}")
    print(f"  ALL DONE!")
    print(f"  Recorded: {success_count}  |  Failed/Locked: {fail_count}")
    print(f"  Saved to: {OUTPUT_DIR}")
    print(f"{'=' * 65}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Script interrupted by user.")
    except Exception as e:
        print(f"\n[ERROR] Uncaught exception in main script execution: {e}")
