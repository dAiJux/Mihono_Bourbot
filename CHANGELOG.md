# Changelog

All notable changes are documented here.

---

## [1.0.1] — 2026-03-06

### Added
- **LDPlayer support**: New platform option alongside Google Play and Steam. Includes dedicated calibration system, click method (background PostMessage to render child window), and per-platform threshold adjustment.
- **Steam / LDPlayer calibration**: Visual debug tool now has "Calibrate LDPlayer" and "Calibrate Steam" buttons. Calibrates 12 screen regions with a guided step-by-step workflow. Calibration data saved to `calibration_ldplayer.json` / `calibration_steam.json`.
- **Platform selector** in GUI launcher and visual debug tool: choose between `google_play`, `ldplayer`, and `steam`.
- **Scheduled race popup** detection: bot recognizes the "scheduled race" banner and proceeds accordingly.
- **Insufficient fans popup** detection with configurable `force_race_insufficient_fans` option.
- **Window Selection tab** in the GUI: pick any visible window as the game target, with a live preview and resolution display.
- `sleep_time_multiplier` config option — scales all functional waits globally.

### Changed
- **Low-energy wit check**: when energy is below the training threshold, the bot now checks **only** the wit training slot. If wit scores well enough, it proceeds; otherwise it rests immediately.
- **Screen detection order**: Race Select is now checked before Skill Select to prevent false positives from background buttons on race screens.
- **Template matching thresholds**: automatically reduced by 0.05 on LDPlayer and Steam (only for high thresholds ≥ 0.78) to compensate for resolution transforms.
- **Event scraper merge** (`scrape_events.py`): now purely additive — never overwrites existing events. Safe to re-run without losing manual edits (`preferred_choice`, etc.).
- Energy thresholds in the decision engine now use configurable values from `config.json` instead of hardcoded values.
- Between-turn delay now uses `action_delay_min / action_delay_max` from config.

### Fixed
- **Launcher freeze on startup**: heavy UI construction moved to deferred init so the splash screen stays responsive.
- **Event title read backwards** (e.g. "Training Extra" instead of "Extra Training"): OCR now sorts by X coordinate for single-line horizontal text.
- **Template matching returning infinity** from OpenCV `matchTemplate` no longer causes crashes (guarded with `math.isfinite`).
- **Prerequisite check** now runs in a background thread instead of blocking the GUI.

---

## [1.0.0] — 2026-02-24

### Added
- Window-only interaction via `PostMessage` (mouse/keyboard unaffected)
- GUI launcher (tkinter) for stat targets, priorities, thresholds, scenario
- 6-level priority decision tree: Race › Infirmary › Rest › Recreation › Training
- Multi-run support with queue management
- Unity Cup scenario: spirit bursts, unity matches, final round
- URA scenario: standard race flow
- OCR via EasyOCR (Speed, Stamina, Power, Guts, Wit, energy, mood)
- Template matching for buttons, icons, race days, injury, rainbow training
- Friendship tracking (icon count, support bars)
- Event database with 500+ entries (game8.co), optimal choice selection
- Emergency stop (F12), pause/resume
- Anti-detection: random offsets, variable delays
- **Skill system** (`scripts/automation/skills.py`): auto-navigate to skill screen, scroll full list, OCR skill names with gradient-based cluster detection, fuzzy-match against configurable wishlist (515 skills), confirm purchase
- **`GameScreen.SKILL_SELECT`** state and `btn_skills` template for skill screen detection
- **`RACE_RESULT`** screen state — `btn_tap` / `btn_race_next_finish` correctly identified
- **`STRATEGY`** screen state — strategy popup detected before `SKILL_SELECT` to avoid `confirm_btn` collision
- **Visual debug diagnostics** (`D` key): multi-mask sweep, per-screen button isolation
- Tools: `tools/capture_templates.py`, `tools/visual_debug.py`, `tools/build_exe.py`, `tools/scrape_events.py`, `tools/calibrate_positions.py`

### Notes
- Tesseract removed — EasyOCR used exclusively
- Project structured into `scripts/automation`, `scripts/decision`, `scripts/gui`, `scripts/vision`