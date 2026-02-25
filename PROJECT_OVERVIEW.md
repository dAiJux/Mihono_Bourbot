# Project Overview

## Architecture

The bot uses a **flat mixin pattern** — all modules live at the package root and are composed into a single `MihonoBourbot` class via multiple inheritance.

```
┌─────────────────────────────────────────────────┐
│                  GUI Launcher                   │
│               (launcher.py)                     │
└──────────────────┬──────────────────────────────┘
                   │ spawns thread
┌──────────────────▼──────────────────────────────┐
│               MihonoBourbot                     │
│                 (bot.py)                        │
│                                                 │
│  CaptureMixin  │  DetectionMixin  │  OcrMixin   │
│  EngineMixin   │  NavigationMixin │  RaceMixin  │
│  SkillsMixin   │  TrainingMixin   │  UnityMixin │
│  EventsMixin   │  ClicksMixin                  │
└─────────────────────────────────────────────────┘
```

---

## Module Responsibilities

| File | Purpose |
|------|---------|
| `bot.py` | Main loop: capture → decide → act → repeat |
| `models.py` | Shared enums: `GameScreen`, `Action` |
| `config.py` | Constants, required template names |
| `capture.py` | Window capture (`PrintWindow` / `BitBlt`), screen calibration |
| `detection.py` | Template matching, `detect_screen()`, screen-specific detectors |
| `ocr.py` | EasyOCR — stats, energy, mood, date reading |
| `training.py` | Training analysis: bursts, friendship, rainbow detection |
| `engine.py` | Decision priority tree (`decide_action`) |
| `events.py` | Event matching, choice scoring, database lookup |
| `navigation.py` | Screen navigation, `advance_turn`, `execute_action` dispatcher |
| `race.py` | Full race flow: selection → strategy → launch → results |
| `skills.py` | Skill screen: scroll, OCR, wishlist matching, purchase |
| `unity.py` | Unity Cup flow: opponents, showdown, results |
| `clicks.py` | Low-level click helpers: `PostMessage`, offsets, waits |
| `launcher.py` | Tkinter GUI for configuration and control |
| `prereqs.py` | Prerequisite checks at startup |

---

## Mixin Pattern

```python
class MihonoBourbot(
    CaptureMixin,
    DetectionMixin,
    OcrMixin,
    TrainingMixin,
    EngineMixin,
    EventsMixin,
    NavigationMixin,
    RaceMixin,
    SkillsMixin,
    UnityMixin,
    ClicksMixin,
):
    def __init__(self, config): ...
```

All mixins share the same `self`, so any mixin can call methods from any other without passing references.

---

## Decision Priority Tree

Every turn, the bot evaluates conditions in strict order:

| Priority | Condition | Action | Key method |
|----------|-----------|--------|------------|
| **0** | `btn_race_start` visible | → Race (mandatory) | `detect_race_day()` |
| **1** | Target / scheduled race | → Race | `detect_target_race()` |
| **2** | Injury present | → Infirmary | `detect_injury()` |
| **3** | Energy < 30% | → Rest | `read_energy_percentage()` |
| **4** | Mood awful / not Great (Classic+) | → Recreation | `detect_mood()` |
| **5** | Default | → Train best stat | `_determine_training_stat()` |

**Screen detection order in `detect_screen()`:**

1. Strategy popup (4 strategy templates)
2. Skill select (`buy_skill`, `learn_btn`, `confirm_btn`)
3. **Race / mandatory race** (`btn_race_start` — checked before MAIN to avoid background button confusion)
4. Race select (`btn_race`)
5. Main screen (2+ main buttons)
6. Training screen (2+ training templates)
7. Inspiration, Unity, Race result, Career complete, Event
8. UNKNOWN

---

## Screen Flow

```
MAIN
 ├── Race day → RACE (mandatory) → RACE_RESULT → MAIN
 ├── btn_races → RACE_SELECT → [STRATEGY] → RACE → RACE_RESULT → MAIN
 ├── btn_training → TRAINING → MAIN
 ├── btn_skills → SKILL_SELECT → MAIN
 ├── btn_rest / btn_recreation → MAIN
 └── Event popup → EVENT → MAIN
```

---

## Skill System

Skills are handled by `SkillsMixin` (`skills.py`):

1. Navigate to skill screen via `btn_skills`
2. Scroll the list with a slow drag (`0.65 → 0.45` of screen height)
3. After each scroll, compare visible `buy_skill` icon positions
4. Stop when same positions appear twice in a row (end of list)
5. For each visible active icon, OCR the skill name using gradient-based cluster detection
6. Fuzzy-match against the configured wishlist (`rapidfuzz`)
7. Select matching skills, then confirm purchase

---

## Event System

Events are matched against `config/event_database.json` (500+ entries from game8.co):

1. Match by character name → character-specific choices
2. Match by support card → support-specific choices
3. Match common events
4. Keyword pattern fallback
5. Default to choice 1

Scrape updated data: `python scrape_events.py`

---

## Window Interaction

### Screenshot Capture

```python
# Primary: PrintWindow (works with hardware-accelerated renderers)
ctypes.windll.user32.PrintWindow(hwnd, dc.GetSafeHdc(), PW_RENDERFULLCONTENT)

# Fallback: BitBlt
mem_dc.BitBlt((0,0), (w,h), img_dc, (x,y), SRCCOPY | CAPTUREBLT)
```

### Click Delivery

```python
# Direct to window — no mouse movement
lp = win32api.MAKELONG(client_x, client_y)
win32gui.PostMessage(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lp)
time.sleep(random.uniform(0.05, 0.15))
win32gui.PostMessage(hwnd, WM_LBUTTONUP, 0, lp)
```

### Scroll (Skill List)

```python
# Slow drag via WM_MOUSEMOVE sequence
win32gui.PostMessage(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lp_start)
for step in range(25):
    win32gui.PostMessage(hwnd, WM_MOUSEMOVE, MK_LBUTTON, lp_interp)
    time.sleep(0.04)
win32gui.PostMessage(hwnd, WM_LBUTTONUP, 0, lp_end)
```

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.8+ |
| Window capture | pywin32 (`PrintWindow`, `BitBlt`) |
| Click injection | pywin32 (`PostMessage`) |
| Template matching | OpenCV (`matchTemplate`, `TM_CCOEFF_NORMED`) |
| OCR | EasyOCR (no external binary, GPU-optional) |
| Fuzzy matching | rapidfuzz (skill name matching) |
| GUI | tkinter (stdlib) |
| Packaging | PyInstaller |

---

## Key Design Decisions

**Flat package structure** — All files at root, no subdirectory nesting. Easier to navigate and import without `__init__` boilerplate.

**Mixin composition** — `MihonoBourbot` inherits from all mixins. Any method can call any other via `self`. Avoids passing module references around.

**`PostMessage` over `pyautogui`** — Sends clicks directly to the window handle. User's mouse stays free. Windows-only trade-off.

**EasyOCR over Tesseract** — No external binary dependency, works at small font sizes, GPU-optional. Slightly slower first load (model download).

**Template-based detection** — Game UI is deterministic. Template matching is faster and more reliable than ML for fixed UI layouts. Per-button masks exclude character overlays that would otherwise reduce confidence.

**Gradient-based OCR for skills** — Instead of OCR'ing the full screen, the bot detects horizontal brightness gradients near each `buy_skill` icon to isolate the title text cluster, then runs EasyOCR on that small crop. More reliable than full-screen OCR at varying positions.