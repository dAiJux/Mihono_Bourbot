# Mihono Bourbot — Umamusume Pretty Derby Training Automation

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)](https://www.microsoft.com/windows)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-active-brightgreen.svg)]()

> **⚠️ Disclaimer**: This bot automates gameplay which may violate the game's Terms of Service. Use at your own risk.

An automation bot for **Umamusume Pretty Derby** training scenarios. Captures the game window, analyzes UI via template matching and OCR, and executes decisions using the Windows API — without taking over your mouse or keyboard.

---

## Features

| Category | Details |
|----------|---------|
| **Interaction** | Window-only clicks via `PostMessage` — mouse and keyboard stay free |
| **Interface** | GUI launcher with stat priorities, thresholds, and scenario selection |
| **Decision engine** | Priority tree: Race › Infirmary › Rest › Recreation › Training |
| **Scenarios** | Unity Cup (spirit bursts, unity matches) + URA |
| **Events** | 500+ events from game8.co with optimal choice selection |
| **Vision** | Template matching (OpenCV) + OCR (EasyOCR) for stats, energy, mood |
| **Skills** | Skill wishlist — auto-scrolls skill screen, selects matching skills |
| **Safety** | Random offsets, variable delays, F12 emergency stop |
| **Debug** | Live overlay (`visual_debug.py`) with D-key diagnostics |

---

## Quick Start

### Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python 3.8+ | [python.org](https://www.python.org/downloads/) |
| Umamusume Pretty Derby | Running in a window (DMM or emulator) |
| EasyOCR models | Downloaded automatically on first run (~500 MB) |

### Installation

```bash
git clone https://github.com/your-org/mihono_bourbot.git
cd mihono_bourbot
pip install -r requirements.txt
```

### Launch

```bash
# GUI (recommended)
python -m scripts

# Vision debug overlay
python tools/visual_debug.py
```

---

## Project Structure

```
mihono_bourbot/
├── scripts/
│   ├── automation/
│   │   ├── clicks.py        # Low-level click helpers
│   │   ├── events.py        # Event matching & choice scoring
│   │   ├── navigation.py    # Screen navigation, turn advance
│   │   ├── race.py          # Full race flow
│   │   ├── skills.py        # Skill screen scroll & selection
│   │   ├── training.py      # Training analysis (bursts, friendship, rainbow)
│   │   └── unity.py         # Unity Cup flow
│   ├── decision/
│   │   ├── engine.py        # Decision priority tree
│   │   └── events.py        # Event decision logic
│   ├── gui/
│   │   ├── config.py        # GUI config panel
│   │   ├── launcher.py      # Tkinter GUI launcher
│   │   └── prereqs.py       # Prerequisite checks at startup
│   ├── vision/
│   │   ├── capture.py       # Window capture, screen calibration
│   │   ├── detection.py     # Template matching, screen identification
│   │   ├── ocr.py           # EasyOCR (stats, energy, mood, dates)
│   │   └── training.py      # Training visual analysis
│   ├── __main__.py          # CLI entry point
│   ├── bot.py               # Main loop orchestrator
│   └── models.py            # Shared enums (GameScreen, Action)
│
├── templates/
│   ├── common/              # Shared buttons (ok, cancel, back…)
│   ├── events/              # Event window templates
│   ├── main_screen/         # Main screen buttons
│   ├── race/                # Race flow templates
│   ├── skills/              # Skill screen templates
│   ├── status/              # Energy, mood, injury templates
│   ├── training/            # Training button templates
│   ├── unity/               # Unity Cup templates
│   └── meta.json            # Template metadata
│
├── config/
│   ├── calibration.json     # Screen region calibration
│   ├── config.json          # User settings
│   ├── event_database.json  # Event choices (500+ entries)
│   ├── races.json           # Race schedule data
│   └── skills.json          # Skill database (515 entries)
│
├── assets/
│   ├── logo-32x32.png
│   └── logo.ico
│
├── tools/
│   ├── build_exe.py         # PyInstaller packaging script
│   ├── calibrate_positions.py # Screen position calibrator
│   ├── capture_templates.py # Interactive template capture tool
│   ├── scrape_events.py     # Event database scraper (game8.co)
│   └── visual_debug.py      # Live debug overlay
│
├── launch_bot.bat           # Windows launch shortcut
├── requirements.txt
└── README.md
```

---

## Configuration

Edit `config/config.json` or use the GUI:

| Setting | Default | Description |
|---------|---------|-------------|
| `training_targets.speed` | 1200 | Target Speed stat |
| `stat_priority` | `["speed", "power", ...]` | Training order |
| `thresholds.energy_low` | 40 | Rest threshold (%) |
| `safety_settings.emergency_stop_key` | `F12` | Emergency stop hotkey |
| `scenario` | `unity_cup` | `unity_cup` or `ura` |

---

## Decision Logic

The bot evaluates conditions in strict priority order each turn:

| Priority | Condition | Action |
|----------|-----------|--------|
| **0** | Mandatory race day (`btn_race_start` visible) | → Race |
| **1** | Scheduled / target race detected | → Race |
| **2** | Injury present | → Infirmary |
| **3** | Energy < 30% | → Rest |
| **4** | Mood awful, or not Great in Classic/Senior | → Recreation |
| **5** | Default | → Train best stat |

---

## Skill System

The bot can check the skill screen at the end of a run and buy skills from a configurable wishlist:

- Navigates to the skill screen via the **Skills** button
- Scrolls through all available skills using a slow, controlled drag
- Uses OCR to read each skill name and matches against the wishlist (fuzzy matching)
- Selects matching skills, then confirms the purchase

Configure the wishlist in `config/config.json` under `skill_wishlist`.

---

## Tools

| Tool | Command | Purpose |
|------|---------|---------|
| Visual debug | `python tools/visual_debug.py` | Live overlay with detection info. Press **D** for diagnostics |
| Template capture | `python tools/capture_templates.py` | Interactive template capture |
| Screen calibration | `python tools/calibrate_positions.py` | Calibrate UI regions |
| Event scraper | `python tools/scrape_events.py` | Update event database from game8.co |
| Build exe | `python tools/build_exe.py` | Package to standalone `.exe` |

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Game window not found | Ensure game is visible (not minimized). Check window title matches known keywords |
| Template matching fails | Re-capture templates at current resolution. Use `visual_debug.py` to diagnose |
| OCR reads wrong values | Use 1920×1080. Verify EasyOCR is installed: `pip install easyocr` |
| Clicks don't register | Try a different emulator (BlueStacks / LDPlayer / MuMu) |
| Screen detected as UNKNOWN | Run `visual_debug.py`, press **D** on the relevant screen |

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) and [FAQ.md](FAQ.md) for more.

---

## Documentation

- [Project Overview](PROJECT_OVERVIEW.md) — Architecture & design decisions
- [Template Guide](TEMPLATE_GUIDE.md) — Full template list and capture tips
- [FAQ](FAQ.md) — Common questions
- [Troubleshooting](TROUBLESHOOTING.md) — Issue resolution
- [Changelog](CHANGELOG.md) — Version history

---

## License

MIT License — see [LICENSE](LICENSE) file.

---

## Acknowledgments

- Event data from [game8.co](https://game8.co/games/Umamusume-Pretty-Derby)
- Template matching via [OpenCV](https://opencv.org/)
- OCR via [EasyOCR](https://github.com/JaidedAI/EasyOCR)
- Window interaction via [pywin32](https://github.com/mhammond/pywin32)