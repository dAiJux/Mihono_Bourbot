# Project Overview

## Architecture

The bot uses a **modular mixin pattern** with four main modules orchestrated by a central class.

```
┌──────────────────────────────────────────────────┐
│                   GUI Launcher                   │
│            (scripts/gui/launcher.py)             │
└──────────────────┬───────────────────────────────┘
                   │ spawns thread
┌──────────────────▼───────────────────────────────┐
│              Mihono Bourbot                     │
│             (scripts/bot.py)                     │
│                                                  │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────┐ │
│   │VisionModule │  │DecisionModule│  │Automation││
│   │  (capture,  │  │  (priority  │  │  Module  ││
│   │   OCR,      │──│   tree,     │──│ (clicks, ││
│   │  templates) │  │   events)   │  │  delays) ││
│   └─────────────┘  └─────────────┘  └─────────┘ │
└──────────────────────────────────────────────────┘
```

---

## Module Responsibilities

| Module | Package | Purpose |
|--------|---------|---------|
| **VisionModule** | `scripts/vision/` | Window capture (`win32gui`), template matching (OpenCV), OCR (Tesseract) |
| **DecisionModule** | `scripts/decision/` | 6-level priority tree, event choice lookup |
| **AutomationModule** | `scripts/automation/` | Click injection (`PostMessage`), race/training flow |
| **Mihono Bourbot** | `scripts/bot.py` | Main loop: capture → decide → act → repeat |
| **GUI** | `scripts/gui/` | Tkinter interface for config and control |

---

## Mixin Pattern

Each module package uses **mixin composition**:

```python
# scripts/vision/__init__.py
class VisionModule(
    CaptureMixin,        # Window capture (capture.py)
    DetectionMixin,      # Template matching (detection.py)
    OcrMixin,            # Tesseract OCR (ocr.py)
    TrainingAnalysisMixin # Training analysis (training.py)
):
    def __init__(self, config):
        ...
```

**Benefits:**
- 🔹 Small, focused files (~200-500 lines each)
- 🔹 Shared `self` at runtime (no passing modules around)
- 🔹 Easy to locate functionality
- 🔹 Clear separation of concerns

---

## Decision Priority Tree

Every turn, the bot evaluates conditions in **strict order**:

| Priority | Condition | Action | Implementation |
|----------|-----------|--------|----------------|
| **0** | Complete Career screen | Stop bot | `detect_screen()` |
| **1** | Race day / Scheduled race | → Race | `detect_race_day()` |
| **2** | Debuff/Injury present | → Infirmary | `detect_injury()` |
| **3** | Rainbow training + energy ≥ threshold | → Rainbow | `detect_rainbow_training()` |
| **4** | Energy < low threshold | → Rest | `read_energy_percentage()` |
| **5** | Mood below target | → Recreation | `detect_mood()` |
| **6** | Default | → Train best stat | `_determine_training_stat()` |

**Code:**
```python
# scripts/decision/engine.py
def decide_action(self) -> Tuple[Action, Optional[str]]:
    if self.vision.detect_race_day(screenshot):
        return (Action.RACE, "raceday")
    if self.vision.detect_injury(screenshot):
        return (Action.INFIRMARY, None)
    # ... continues through priorities
```

---

## Event System

Events are matched against `config/event_database.json`:

```json
{
  "character_events": {
    "Sakura Bakushin O": [
      {"title_pattern": "Explosive", "choice": 1, "reason": "+Speed +Guts"}
    ]
  },
  "support_card_events": { ... },
  "common_events": { ... },
  "keyword_patterns": {
    "keywords": ["training", "practice"],
    "patterns": ["+Speed", "stat", "boost"]
  }
}
```

**Matching algorithm:**
1. Try character-specific events
2. Try support card events
3. Try common events
4. Fall back to keyword patterns
5. Default to first choice if no match

**Data source:** [game8.co](https://game8.co/games/Umamusume-Pretty-Derby)

---

## Window Interaction

### Screenshot Capture

```python
# Method 1: PrintWindow (primary)
hwnd_dc = win32gui.GetWindowDC(hwnd)
mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), PW_RENDERFULLCONTENT)

# Method 2: BitBlt (fallback)
desktop_dc = win32gui.GetWindowDC(hdesktop)
mem_dc.BitBlt((0, 0), (w, h), img_dc, (x, y), win32con.SRCCOPY | CAPTUREBLT)
```

### Click Delivery

```python
# Direct to window (no mouse movement)
lp = win32api.MAKELONG(client_x, client_y)
win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
time.sleep(random.uniform(0.05, 0.15))  # Humanlike delay
win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lp)
```

---

## File Structure

```
mihono_bourbot/
├── scripts/                               # Main package
│   ├── __init__.py                        # Exports MihonoBourbot, GameScreen, Action
│   ├── __main__.py                        # Entry point (CLI args)
│   ├── bot.py                             # Orchestrator (main loop)
│   ├── models.py                          # Shared enums
│   │
│   ├── vision/                            # Vision module
│   │   ├── __init__.py                    # VisionModule (composite)
│   │   ├── capture.py                     # Window capture, calibration
│   │   ├── detection.py                   # Template matching, screen detection
│   │   ├── ocr.py                         # Tesseract OCR (stats, energy, mood)
│   │   └── training.py                    # Training analysis (friends, bursts)
│   │
│   ├── automation/                        # Automation module
│   │   ├── __init__.py                    # AutomationModule (composite)
│   │   ├── clicks.py                      # Low-level click helpers
│   │   ├── race.py                        # Race flow (prep, run, results)
│   │   ├── training.py                    # Training execution
│   │   ├── events.py                      # Event handling
│   │   ├── unity.py                       # Unity Cup flow
│   │   └── navigation.py                  # Screen navigation, turn advance
│   │
│   ├── decision/                          # Decision module
│   │   ├── __init__.py                    # DecisionModule (composite)
│   │   ├── engine.py                      # Priority tree
│   │   └── events.py                      # Event choice scoring
│   │
│   └── gui/                               # GUI module
│       ├── __init__.py                    # Exports main(), BotLauncher
│       ├── launcher.py                    # Main window (tkinter)
│       ├── config.py                      # Config defaults & constants
│       └── prereqs.py                     # Prerequisite checks
│
├── tools/                                 # Standalone utilities
│   ├── capture_templates.py               # Interactive template capture
│   ├── calibrate_positions.py             # Screen position calibrator
│   ├── visual_debug.py                    # Debug overlay (press D)
│   ├── scrape_events.py                   # Event database scraper
│   └── build_exe.py                       # PyInstaller script
│
├── config/                                # Configuration
│   ├── config.json                        # User settings
│   ├── calibration.json                   # Screen calibration
│   └── event_database.json                # Event choices (500+ entries)
│
├── templates/                             # Template images (user-captured)
│   ├── main_screen/                       # Main hub buttons
│   ├── training/                          # Training icons & burst indicators
│   ├── race/                              # Race flow elements
│   ├── events/                            # Event choice buttons
│   ├── unity/                             # Unity Cup elements
│   ├── status/                            # Mood & energy indicators
│   └── common/                            # Shared navigation buttons
│
└── logs/                                  # Runtime logs
    └── bot.log                            # Main log file
```

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Language** | Python 3.8+ | Core language |
| **Window Capture** | pywin32 (`win32gui`, `win32ui`) | Screenshot via WinAPI |
| **Click Injection** | pywin32 (`PostMessage`) | Sends clicks without moving mouse |
| **Template Matching** | OpenCV (`cv2.matchTemplate`) | Detects UI elements |
| **OCR** | Tesseract + pytesseract | Reads stats, energy, mood |
| **GUI** | tkinter (stdlib) | Configuration interface |
| **Packaging** | PyInstaller | Standalone .exe builds |

---

## Data Flow

```
┌─────────┐
│  Start  │
└────┬────┘
     │
     ▼
┌──────────────────┐
│ Capture Window   │ (VisionModule.take_screenshot)
│ → np.ndarray     │
└────┬─────────────┘
     │
     ▼
┌──────────────────┐
│ Detect Screen    │ (VisionModule.detect_screen)
│ → GameScreen     │
└────┬─────────────┘
     │
     ▼
┌──────────────────┐
│ Read State       │ (OCR: stats, energy, mood)
│ → Dict           │ (Template: injury, race day, etc.)
└────┬─────────────┘
     │
     ▼
┌──────────────────┐
│ Decide Action    │ (DecisionModule.decide_action)
│ → Action, detail │
└────┬─────────────┘
     │
     ▼
┌──────────────────┐
│ Execute Action   │ (AutomationModule.execute_action)
│ → clicks, waits  │
└────┬─────────────┘
     │
     ▼
┌──────────────────┐
│ Advance Turn     │ (AutomationModule.advance_turn)
│ → handle dialogs │
└────┬─────────────┘
     │
     └──────► (loop)
```

---

## Key Design Decisions

### Why Mixins?

**Problem:** Large monolithic classes (2000+ lines).  
**Solution:** Split into focused mixins (200-500 lines each).  
**Trade-off:** More files, but easier to navigate and maintain.

### Why `PostMessage` instead of `pyautogui`?

**Problem:** `pyautogui` moves the user's mouse.  
**Solution:** `PostMessage` sends clicks directly to window handle.  
**Trade-off:** Windows-only, some emulators block it.

### Why Tesseract OCR?

**Problem:** Game stats change dynamically (can't template match numbers).  
**Solution:** OCR reads digits from screen.  
**Trade-off:** Requires external dependency, can misread at low resolution.

### Why not machine learning?

**Problem:** Game UI is deterministic (buttons always in same place).  
**Solution:** Template matching is simpler, faster, and more reliable.  
**Trade-off:** Need to recapture templates if UI changes.

---

## Future Improvements

- 🔸 Multi-scenario support (Grand Live, etc.)
- 🔸 Web dashboard for remote monitoring
- 🔸 Docker support for headless operation
- 🔸 Skill inheritance optimization
- 🔸 Auto-template recapture on UI changes
