# Project Overview

## Architecture

The bot uses a **composition pattern** — specialized modules are instantiated and wired together in the main `MihonoBourbot` class.

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
│  self.vision     = VisionModule(config)         │
│  self.decision   = DecisionModule(config, …)    │
│  self.automation = AutomationModule(config, …)  │
└─────────────────────────────────────────────────┘

VisionModule (scripts/vision/)
├── CaptureMixin        — window capture, game_rect
├── DetectionMixin      — template matching, detect_screen
├── OcrMixin            — stats, energy, mood, event text
└── TrainingAnalysisMixin — burst/friendship/rainbow

DecisionModule (scripts/decision/)
├── engine.py           — priority tree (decide_action)
└── events.py           — event choice scoring

AutomationModule (scripts/automation/)
├── ClicksMixin         — PostMessage clicks, waits
├── NavigationMixin     — screen navigation, turn advance
├── EventsMixin         — event matching & choice execution
├── RaceMixin           — full race flow
├── SkillsMixin         — skill screen scroll & selection
├── TrainingMixin       — training execution, claw machine
└── UnityMixin          — Unity Cup flow
```

---

## Module Responsibilities

| File | Purpose |
|------|---------|
| `bot.py` | Main loop: capture → decide → act → repeat |
| `models.py` | Shared enums: `GameScreen`, `Action` |
| **Vision** | |
| `vision/__init__.py` | `VisionModule` — composes capture, detection, OCR, training analysis |
| `vision/capture.py` | Window capture (`PrintWindow` / `BitBlt`), game_rect calibration |
| `vision/detection.py` | Template matching, `detect_screen()`, screen-specific detectors |
| `vision/ocr.py` | EasyOCR — stats, energy, mood, date, event text reading |
| `vision/training.py` | Training analysis: bursts, friendship, rainbow detection |
| **Decision** | |
| `decision/engine.py` | Decision priority tree (`decide_action`) |
| `decision/events.py` | Event decision logic |
| **Automation** | |
| `automation/clicks.py` | Low-level click helpers: `PostMessage`, offsets, waits |
| `automation/events.py` | Event matching, choice scoring, database lookup |
| `automation/navigation.py` | Screen navigation, `advance_turn`, `execute_action` dispatcher |
| `automation/race.py` | Full race flow: selection → strategy → launch → results |
| `automation/skills.py` | Skill screen: scroll, OCR, wishlist matching, purchase |
| `automation/training.py` | Training execution, claw machine handling |
| `automation/unity.py` | Unity Cup flow: opponents, showdown, results |
| **GUI** | |
| `gui/launcher.py` | Tkinter GUI for configuration and control |
| `gui/config.py` | GUI config panel |
| `gui/prereqs.py` | Prerequisite checks at startup |

---

## Composition Pattern

```python
class MihonoBourbot:
    def __init__(self, config):
        self.vision     = VisionModule(config)
        self.decision   = DecisionModule(config, self.vision)
        self.automation = AutomationModule(config, self.vision, self.decision)
```

`VisionModule` itself is built from mixins:

```python
class VisionModule(CaptureMixin, DetectionMixin, OcrMixin, TrainingAnalysisMixin):
    def __init__(self, config): ...
```

`AutomationModule` composes clicks, navigation, race, skills, training, unity, and events mixins.

All mixins within a module share the same `self`, so any mixin can call methods from any other without passing references.

---

## Decision Priority Tree

Every turn, the bot evaluates conditions in strict order:

| Priority | Condition | Action | Key method |
|----------|-----------|--------|------------|
| **0** | `btn_race_start` visible | → Race (mandatory) | `detect_race_day()` |
| **1** | Target / scheduled race | → Race | `detect_target_race()` |
| **2** | Injury present | → Infirmary | `detect_injury()` |
| **3** | Energy < `energy_low` (config, default 40%) | → Rest | `read_energy_percentage()` |
| **4** | Energy < `energy_training` (default 50%) | → Check wit only, rest if not worth it | `score_single_training()` |
| **5** | Mood awful / not Great (Classic+) | → Recreation | `detect_mood()` |
| **6** | Default | → Train best stat | `_determine_training_stat()` |

**Screen detection order in `detect_screen()`:**

1. Recreation popup (`recreation_popup` + `trainee_uma` guard)
2. Strategy popup (≥4 strategy templates)
3. Pre-compute shared templates (`btn_race`, `learn_btn`, `btn_begin_showdown`, `btn_race_launch`)
4. Insufficient fans popup (banner match)
5. Scheduled race popup (banner match + exclusion guards)
6. Race select (`btn_race` without `btn_race_launch`)
7. Race select (`btn_race_confirm` without skill/confirm buttons)
8. Race / Race start (`btn_race_start` / `btn_race_start_ura` + view results / strategy / launch)
9. Main screen (≥2 main buttons)
10. Training (≥2 training templates or `white_burst`)
11. Event (`detect_event_type()`)
12. Unity Cup (6 unity templates, non-URA only)
13. Skill select (`buy_skill`, `learn_btn`, `confirm_btn`)
14. Claw machine (`btn_claw_machine` or `claw_prizes`)
15. Inspiration (`btn_inspiration`)
16. Race — launch only (`btn_race_launch`)
17. Race result (`btn_race_next_finish`, `btn_tap`, `btn_next`)
18. Try again (`btn_try_again`)
19. Career complete (`complete_career`)
20. UNKNOWN (fallback)

---

## Screen Flow

```
MAIN
 ├── Race day → RACE_START → [STRATEGY] → RACE → RACE_RESULT → MAIN
 ├── btn_races → RACE_SELECT → [STRATEGY] → RACE → RACE_RESULT → MAIN
 ├── Insufficient fans → INSUFFICIENT_FANS → MAIN
 ├── Scheduled race popup → SCHEDULED_RACE_POPUP → RACE_SELECT → …
 ├── btn_training → TRAINING → MAIN
 ├── btn_skills → SKILL_SELECT → MAIN
 ├── btn_rest / btn_recreation → MAIN
 ├── Recreation popup → RECREATION → MAIN
 ├── Event popup → EVENT → MAIN
 └── Unity (non-URA) → UNITY → [CLAW_MACHINE] → MAIN
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

**Manual window selection** — The GUI provides a **Window** tab listing all visible windows. The user picks the one running the game. The saved title is persisted in `config.json` and checked first on startup. Falls back to keyword-based auto-detect if nothing is saved. This supports any emulator or player.

**Resolution-agnostic** — Templates are captured at a reference width (stored in `templates/meta.json`). At runtime the bot computes a scale factor from the actual game width and resizes all templates accordingly. Fractional coordinates in `calibration.json` adapt to any size. Windowed-mode chrome is automatically excluded via `ClientToScreen`/`GetClientRect`.

**Flat package structure** — All files at root, no subdirectory nesting. Easier to navigate and import without `__init__` boilerplate.

**Mixin composition** — `MihonoBourbot` inherits from all mixins. Any method can call any other via `self`. Avoids passing module references around.

**`PostMessage` over `pyautogui`** — Sends clicks directly to the window handle. User's mouse stays free. Windows-only trade-off.

**EasyOCR over Tesseract** — No external binary dependency, works at small font sizes, GPU-optional. Slightly slower first load (model download).

**Template-based detection** — Game UI is deterministic. Template matching is faster and more reliable than ML for fixed UI layouts. Per-button masks exclude character overlays that would otherwise reduce confidence.

**Gradient-based OCR for skills** — Instead of OCR'ing the full screen, the bot detects horizontal brightness gradients near each `buy_skill` icon to isolate the title text cluster, then runs EasyOCR on that small crop. More reliable than full-screen OCR at varying positions.