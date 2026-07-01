# Brilliant.org Activity Recorder & Auto-Solver

This project provides an automated pipeline to record, interact with, and solve learning activities on Brilliant.org. It launches a local instance of Microsoft Edge using your existing logged-in profile, initiates high-quality synchronized audio and video recording, sends a message to the Koji tutor panel, and automatically solves the interactive question cards step-by-step.

---

## Features
- **Local Edge Profile Reuse**: Automatically picks up your logged-in session, ensuring access to premium/locked courses without requiring explicit credentials in the script.
- **Synchronized Audio & Video Recording**:
  - Captures high-definition screen video via FFmpeg's `gdigrab`.
  - Captures system loopback audio via `pyaudiowpatch`.
  - Merges audio and video streams into a final MP4 container.
- **Tutor Interaction**: Opens the Koji tutor chat ("chat with tutor") and automatically requests an explanation.
- **Robust Auto-Solver**:
  - Resolves standard multiple-choice and radio-button cards.
  - Automatically identifies fill-in-the-blank text inputs and feeds them responses.
  - **Shadow DOM Slot & Drag-and-Drop Matching**: Identifies custom-interactive programming editor slots (such as those on *Thinking in Code*), targets correct draggable blocks, simulates precise drop movements, and tracks filled vs. empty slots dynamically using text-content presence.
  - Backtracks and tries alternative combinations systematically if an attempt fails.

---

## Prerequisites

1. **Operating System**: Windows (required for PyAudioWPatch WASAPI loopback and `gdigrab` screen capture).
2. **Microsoft Edge**: Installed and logged into [Brilliant.org](https://brilliant.org).
3. **FFmpeg**: Must be installed.
   - Install using Windows Package Manager:
     ```powershell
     winget install Gyan.FFmpeg
     ```
   - Verify it is available on your system `PATH`, or set the `FFMPEG_PATH` environment variable.

---

## Installation & Setup

1. **Clone the Repository**:
   ```bash
   git clone <your-repo-url>
   cd myproject
   ```

2. **Set Up a Virtual Environment & Install Dependencies**:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   playwright install chromium
   ```

3. **Configure Environment Variables**:
   Copy `.env.example` to `.env` and fill in any keys if using external database logging (optional):
   ```bash
   copy .env.example .env
   ```

---

## Usage

### 1. Scan for Koji-Enabled Activities
Run `scan_koji_pages.py` to scan through free preview pages (read from `free_previews.txt`) and filter the ones that have Koji tutor buttons. This saves results to `koji_pages.txt`.
```bash
python scan_koji_pages.py
```

### 2. Run the Recorder & Auto-Solver
Run `record_with_koji.py`. This reads from `koji_pages.txt`, kills active Edge instances, opens the pages inside Edge, starts recording, types the message to Koji, solves the cards, and saves the final merged video to `recordings/koji_sessions/`.
```bash
python record_with_koji.py
```

---

## Core Script Logic (Auto-Solver Mechanics)

The script uses a complex state-machine loop to progress through each question card:
1. **Continue Button Detection**: If the card is already solved, it clicks "Continue" or "Next" to advance.
2. **Try Again / Start Over Handling**: If an attempt was incorrect, it clicks "Try again" or "Start over" to reset card states and systematically register incorrect paths.
3. **Choice Selection**:
   - For standard options, it clicks the choice.
   - For slot-based drag-and-drop puzzles (e.g., matching coordinates in a workspace):
     - Pierces the Shadow DOM to find slot elements (`.dandyDropBeacon` or `slot_line_`).
     - Ignores choice bank slots (filtering out IDs containing `"bank"`).
     - Finds the first slot where `inner_text()` is empty (indicating no block has been dropped inside).
     - Simulates dragging the choice block to the target slot center.
4. **Verification**: Compares the number of filled slots before and after dragging to confirm if the block was successfully attached.
5. **Check Answer**: Once requirements are satisfied, it submits the response.

---

## Troubleshooting

- **Profile Lock Error**: Make sure Microsoft Edge is fully closed before running the script. The script automatically runs `taskkill /F /IM msedge.exe` before launch to release the profile directory lock.
- **Audio Capture Failed**: Ensure your default Windows playback device is active. PyAudioWPatch relies on your active WASAPI loopback device.
