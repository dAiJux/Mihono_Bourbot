# Mihono Bourbot — Umamusume Pretty Derby Training Automation

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)](https://www.microsoft.com/windows)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-stable-brightgreen.svg)]()

> **⚠️ Disclaimer**: This bot automates gameplay which may violate the game's Terms of Service. Use at your own risk.

An advanced desktop automation bot for **Umamusume Pretty Derby** training scenarios. Captures the game window, analyzes UI via template matching and OCR, and executes decisions using Windows API—all without taking over your mouse or keyboard.

---

## ✨ Features

| Category | Features |
|----------|----------|
| **Interaction** | Window-only clicks via `win32gui` / `PostMessage` — mouse stays free |
| **Interface** | Full-featured GUI launcher with drag-and-drop stat priorities |
| **Intelligence** | 6-level decision tree: Race › Infirmary › Rainbow › Rest › Recreation › Training |
| **Scenarios** | Unity Cup (with spirit bursts & unity matches) + URA scenario |
| **Events** | 500+ events from game8.co with optimal choice selection |
| **Vision** | OCR stat reading (Speed/Stamina/Power/Wit/Guts/Energy/Mood) + template matching |
| **Safety** | Random click offsets, variable delays, F12 emergency stop |
| **Control** | Pause/Resume, multi-run queue, vision test mode |

---

## 🚀 Quick Start

### Prerequisites

| Requirement | Link |
|-------------|------|
| Python 3.8+ | [Download](https://www.python.org/downloads/) |
| Tesseract OCR | [Windows Installer](https://github.com/UB-Mannheim/tesseract/wiki) |
| Umamusume Pretty Derby | Running in a window (DMM/Emulator) |

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/your-org/mihono_bourbot.git
cd mihono_bourbot

# 2. Install dependencies
pip install -r requirements.txt

# 3. Verify Tesseract installation
tesseract --version
```

### First-Time Setup

**Step 1: Capture Templates** (required)

```bash
python tools/capture_templates.py
```

Follow on-screen instructions to capture UI elements. See [TEMPLATE_GUIDE.md](docs/TEMPLATE_GUIDE.md) for the complete list.

**Step 2: Launch GUI**

```bash
python -m scripts
```

Or double-click `launch_bot.bat` (Windows).

**Step 3: Configure & Run**

1. Set stat targets (Speed, Stamina, Power, Wit, Guts)
2. Reorder priority via drag-and-drop
3. Choose scenario (Unity Cup / URA)
4. Click **▶ Start Bot**

---

## 📂 Project Structure

```
mihono_bourbot/
├── scripts/                    # Core bot package
│   ├── vision/                 # Screen capture, OCR, template matching
│   ├── automation/             # Click injection, race/training flow
│   ├── decision/               # Priority engine, event handling
│   └── gui/                    # Tkinter launcher interface
├── tools/                      # Standalone utilities
│   ├── capture_templates.py    # Interactive template capture
│   ├── visual_debug.py         # Debug overlay (press D for diagnostics)
│   └── scrape_events.py        # Event database scraper
├── config/                     # Configuration files
│   ├── config.json             # User settings
│   ├── calibration.json        # Screen calibration
│   └── event_database.json     # Event choices (game8.co data)
├── templates/                  # User-captured template images
│   ├── main_screen/, training/, race/, events/, unity/
└── logs/                       # Runtime logs
```

See [PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md) for architecture details.

---

## ⚙️ Configuration

Edit `config/config.json` or use the GUI:

| Setting | Default | Description |
|---------|---------|-------------|
| `training_targets.speed` | 1200 | Target Speed stat |
| `stat_priority` | `["speed", "power", ...]` | Training order |
| `thresholds.energy_low` | 40 | Rest threshold (%) |
| `safety_settings.emergency_stop_key` | `F12` | Emergency stop hotkey |
| `scenario` | `unity_cup` | Scenario type (`unity_cup` or `ura`) |

---

## 🎯 Decision Logic

The bot evaluates conditions in strict order every turn:

| Priority | Condition | Action |
|----------|-----------|--------|
| **1** | Mandatory/scheduled race detected | → Race |
| **2** | Debuff/injury present | → Infirmary |
| **3** | Rainbow training available + energy ≥ threshold | → Rainbow Train |
| **4** | Energy < low threshold | → Rest |
| **5** | Mood below target | → Recreation |
| **6** | Default | → Train highest-priority stat not at target |

---

## 🎮 Event Handling

Events are matched against `config/event_database.json` (500+ entries from [game8.co](https://game8.co)):

- **Character events** (e.g., Sakura Bakushin O)
- **Support card events** (e.g., Kitasan Black SSR Speed)
- **Common events**
- **Keyword-based fallback patterns**

Update database: `python tools/scrape_events.py`

---

## 🛠️ CLI Usage

```bash
# Single run (headless)
python -m scripts --cli

# Multiple runs
python -m scripts --cli --runs 5

# Vision test mode
python -m scripts --cli --test
```

---

## 📦 Building an Executable

```bash
pip install pyinstaller
python tools/build_exe.py
```

Output: `dist/Mihono Bourbot/Mihono Bourbot.exe` (~80MB)

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| "Game window not found" | Ensure game is visible (not minimized). Check window title matches keywords in `VisionModule.GAME_WINDOW_TITLES` |
| Template matching fails | Re-capture templates at current resolution. Lower `template_match_threshold` to 0.7 |
| OCR reads wrong values | Verify Tesseract installed. Use 1080p for best results |
| Clicks don't register | Try different emulator (BlueStacks/LDPlayer). Some block `PostMessage` |

See [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) and [FAQ.md](docs/FAQ.md).

---

## 📚 Documentation

- [Project Overview](docs/PROJECT_OVERVIEW.md) — Architecture & design
- [Template Guide](docs/TEMPLATE_GUIDE.md) — How to capture templates
- [FAQ](docs/FAQ.md) — Common questions
- [Troubleshooting](docs/TROUBLESHOOTING.md) — Issue resolution
- [Changelog](docs/CHANGELOG.md) — Version history

---

## 🤝 Contributing

This is a private project for internal team use. Team members with access:

1. Create feature branch: `git checkout -b feature/amazing-feature`
2. Commit changes: `git commit -m 'Add amazing feature'`
3. Push branch: `git push origin feature/amazing-feature`
4. Open Pull Request

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) file.

---

## 🙏 Acknowledgments

- Event data from [game8.co](https://game8.co/games/Umamusume-Pretty-Derby)
- Template matching via [OpenCV](https://opencv.org/)
- OCR via [Tesseract](https://github.com/tesseract-ocr/tesseract)
- Window interaction via [pywin32](https://github.com/mhammond/pywin32)
