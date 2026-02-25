import os
import sys
import time
import json
import cv2
import numpy as np
import ctypes

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import win32gui
    import win32ui
except ImportError:
    print("pywin32 is required. Install it with: pip install pywin32")
    sys.exit(1)

from scripts.vision import VisionModule
from scripts.gui.config import REQUIRED_TEMPLATES

TEMPLATES_DIR = "templates"

_MAIN_SCREEN = {"btn_training", "btn_rest", "btn_rest_summer", "btn_recreation",
                "btn_races", "btn_infirmary", "btn_inspiration"}
_RACE = {"btn_race", "btn_race_confirm", "btn_race_launch", "btn_race_start",
         "btn_race_start_ura", "btn_race_next_finish", "btn_change_strategy",
         "strategy_front", "strategy_pace", "strategy_late", "strategy_end",
         "scheduled_race", "target_race", "race_view_results_off", "race_view_results_on"}
_UNITY = {"btn_begin_showdown", "btn_launch_final_unity", "btn_next_unity",
          "btn_see_unity_results", "btn_select_opponent", "btn_unity_launch",
          "unity_opponent_card", "unity_training", "btn_claw_machine"}
_EVENT = {"event_choice", "event_scenario_window", "event_support_window", "event_trainee_window"}
_STATUS = {"mood_awful", "mood_bad", "mood_good", "mood_great", "mood_normal",
           "energy_bar_depleted", "energy_bar_empty", "energy_bar_full"}

def _template_category(name: str) -> str:
    if name in _MAIN_SCREEN:
        return "main_screen"
    if name in _RACE:
        return "race"
    if name in _UNITY:
        return "unity"
    if name in _EVENT:
        return "events"
    if name in _STATUS:
        return "status"
    if name.startswith(("training_", "type_", "friend_bar_", "rainbow", "blue_burst", "spirit_burst")):
        return "training"
    return "common"

def _template_path(name: str) -> str:
    """Return the save path for a template, creating the sub-folder if needed."""
    cat = _template_category(name)
    folder = os.path.join(TEMPLATES_DIR, cat)
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, f"{name}.png")

def _find_existing(name: str):
    """Find an existing template by name across all sub-folders."""
    from pathlib import Path
    for p in Path(TEMPLATES_DIR).rglob(f"{name}.png"):
        return str(p)
    return None

def _save_ref_width(width: int):
    """Save the game window width as reference for template scaling."""
    meta_path = os.path.join(TEMPLATES_DIR, "meta.json")
    meta = {}
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    if meta.get("reference_width") != width:
        meta["reference_width"] = width
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        print(f"[meta] Reference width saved: {width}px")
    else:
        print(f"[meta] Reference width already set: {width}px")

def list_windows():
    results = []

    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title:
                results.append((hwnd, title))

    win32gui.EnumWindows(callback, None)
    return results

def capture_window(hwnd) -> np.ndarray:
    rect = win32gui.GetWindowRect(hwnd)
    w = rect[2] - rect[0]
    h = rect[3] - rect[1]
    if w <= 0 or h <= 0:
        raise RuntimeError("Window has zero size")

    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(mfc_dc, w, h)
    save_dc.SelectObject(bitmap)

    PW_RENDERFULLCONTENT = 0x00000002
    ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), PW_RENDERFULLCONTENT)

    bmp_info = bitmap.GetInfo()
    bmp_data = bitmap.GetBitmapBits(True)
    img = np.frombuffer(bmp_data, dtype=np.uint8)
    img = img.reshape((bmp_info["bmHeight"], bmp_info["bmWidth"], 4))

    win32gui.DeleteObject(bitmap.GetHandle())
    save_dc.DeleteDC()
    mfc_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwnd_dc)

    return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

def select_roi(image: np.ndarray, window_name: str = "Select Region"):
    print("  Draw a rectangle around the element, then press ENTER or SPACE.")
    print("  Press C to cancel.")

    h, w = image.shape[:2]
    scale = 1.0
    if h > 900:
        scale = 900 / h
        display = cv2.resize(image, (int(w * scale), int(h * scale)))
    else:
        display = image.copy()

    roi = cv2.selectROI(window_name, display, fromCenter=False, showCrosshair=True)
    cv2.destroyWindow(window_name)

    if roi[2] == 0 or roi[3] == 0:
        return None

    x = int(roi[0] / scale)
    y = int(roi[1] / scale)
    rw = int(roi[2] / scale)
    rh = int(roi[3] / scale)

    return image[y : y + rh, x : x + rw]

def interactive_capture():
    print("=" * 60)
    print("  Mihono Bourbot — Template Capture Tool")
    print("=" * 60)
    os.makedirs(TEMPLATES_DIR, exist_ok=True)

    windows = list_windows()
    game_windows = [
        (hwnd, title)
        for hwnd, title in windows
        if any(kw in title.lower() for kw in VisionModule.GAME_WINDOW_TITLES)
        and not any(kw in title.lower() for kw in VisionModule.EXCLUDED_WINDOW_KEYWORDS)
    ]

    if game_windows:
        print("\nDetected game windows:")
        for i, (hwnd, title) in enumerate(game_windows):
            print(f"  [{i}] {title}")
        choice = input("Select window number (or press Enter for first): ").strip()
        idx = int(choice) if choice else 0
        hwnd = game_windows[idx][0]
    else:
        print("\nNo game window detected automatically.")
        print("All visible windows:")
        for i, (hwnd, title) in enumerate(windows[:30]):
            print(f"  [{i}] {title}")
        choice = input("Select window number: ").strip()
        idx = int(choice) if choice else 0
        hwnd = windows[idx][0]

    print(f"Using window: {win32gui.GetWindowText(hwnd)}")

    rect = win32gui.GetWindowRect(hwnd)
    win_w = rect[2] - rect[0]
    _save_ref_width(win_w)

    while True:
        print("\n" + "-" * 40)
        print("Commands:")
        print("  [c] Capture a new template")
        print("  [a] Capture ALL required templates (guided)")
        print("  [f] Take a full screenshot")
        print("  [l] List existing templates")
        print("  [q] Quit")
        cmd = input("> ").strip().lower()

        if cmd == "q":
            break
        elif cmd == "l":
            from pathlib import Path
            files = sorted(str(p.relative_to(TEMPLATES_DIR)) for p in Path(TEMPLATES_DIR).rglob("*.png"))
            if files:
                for f in sorted(files):
                    print(f"    {f}")
            else:
                print("    (no templates yet)")
        elif cmd == "f":
            img = capture_window(hwnd)
            path = os.path.join(TEMPLATES_DIR, f"screenshot_{int(time.time())}.png")
            cv2.imwrite(path, img)
            print(f"  Saved full screenshot: {path}")
        elif cmd == "a":
            print(f"\n  Guided capture for {len(REQUIRED_TEMPLATES)} templates.")
            print("  Navigate to the right screen in-game, then draw a rectangle.")
            print("  Press C or ESC to skip a template.\n")
            for name in REQUIRED_TEMPLATES:
                existing = _find_existing(name)
                status = " (exists, will overwrite)" if existing else ""
                print(f"\n  >> {name}{status}")
                input("     Press Enter when the element is visible on screen...")
                img = capture_window(hwnd)
                roi = select_roi(img, f"Select: {name}")
                if roi is None:
                    print(f"     Skipped {name}")
                    continue
                path = _template_path(name)
                cv2.imwrite(path, roi)
                print(f"     Saved: {path} ({roi.shape[1]}x{roi.shape[0]}px)")
            print("\n  Guided capture complete!")
        elif cmd == "c":
            name = input("  Template name (e.g. btn_training, icon_race): ").strip()
            if not name:
                print("  Name cannot be empty.")
                continue

            img = capture_window(hwnd)
            roi = select_roi(img)
            if roi is None:
                print("  Cancelled.")
                continue

            filename = f"{name}.png"
            path = _template_path(name)
            cv2.imwrite(path, roi)
            print(f"  Saved template: {path}  ({roi.shape[1]}x{roi.shape[0]}px)")
        else:
            print("  Unknown command.")

    print("Done.")

if __name__ == "__main__":
    interactive_capture()