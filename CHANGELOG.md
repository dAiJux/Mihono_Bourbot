# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2025-02-18

### Added

#### Core Features
- **Window-only interaction** using `pywin32` `PostMessage` clicks (mouse/keyboard unaffected)
- **GUI launcher** (tkinter) for configuring stat targets, priorities, thresholds, and scenario
- **6-level priority decision tree**: Race › Infirmary › Rainbow › Rest › Recreation › Training
- **Multi-run support** with queue management from GUI

#### Scenarios
- **Unity Cup scenario** with full support for:
  - Spirit bursts (white/blue)
  - Unity matches
  - Final round flow
- **URA scenario** with standard race flow

#### Vision & Detection
- **OCR stat reading** (Speed, Stamina, Power, Wit, Guts, energy %, mood)
- **Template matching** for buttons, icons, race days, injury markers, rainbow training
- **Friendship tracking** (counts icons & support bars)
- **Card type detection** (Speed/Stamina/Power/Wit/Guts/Friend)
- **Goal & scheduled race detection**

#### Events
- **Event database** with 500+ events scraped from game8.co
- **Optimal choice selection** based on event matching
- **Fallback keyword patterns** for unknown events
- **Event scraper tool** (`tools/scrape_events.py`)

#### Safety & Control
- **Emergency stop** (default: F12, configurable)
- **Pause / Resume** functionality
- **Anti-ban measures**: random click offsets, variable delays, human-like pauses

#### Tools & Utilities
- **Template capture tool** (`tools/capture_templates.py`) - interactive UI element capture
- **Vision test mode** (GUI or CLI) - continuous recognition test
- **PyInstaller build script** (`tools/build_exe.py`) - standalone .exe packaging
- **Quick presets** (Sprint/Mile/Medium/Long stat configurations)
- **Prerequisite checker** (Python packages, Tesseract, templates)

#### Architecture
- **Modular package structure** with mixin pattern:
  - `scripts/vision/` - capture, OCR, template matching
  - `scripts/automation/` - clicks, race/training flow
  - `scripts/decision/` - priority engine, event handling
  - `scripts/gui/` - tkinter interface
- **Template organization** by game screen (main_screen, training, race, events, unity, status, common)

---

## [Unreleased]

### Planned
- MANT Scenario
- Skills management
- Training optimization
- Improved GUI
