# Changelog

All notable changes are documented here.

---

## [1.0.1] — 2026-03-01

### Added
- **Window Selection tab** in the GUI: pick any visible window as the game target, with a live preview and resolution display. Supports any emulator or player without editing code.
- `window_title` config field — persists the selected window across sessions. Falls back to auto-detect when empty.
- `sleep_time_multiplier` support in the `wait()` helper — scales all functional waits globally.

### Changed
- **Low-energy wit check**: when energy is below the training threshold, the bot now checks **only** the wit training slot instead of scanning all five. If wit scores well enough, it proceeds; otherwise it rests immediately. Eliminates unnecessary clicks.
- Energy thresholds in the decision engine now use `thresholds.energy_low` from config instead of hardcoded `30`.
- Between-turn delay now uses `automation_settings.action_delay_min / action_delay_max` from config instead of hardcoded `1–3 s`.
- `find_game_window()` checks the saved `window_title` first, then falls back to keyword-based auto-detect.

### Fixed
- Hardcoded energy values (30/35/45) replaced with configurable thresholds throughout `engine.py` and `training.py`.
- `btn_race_start` is now checked at the top of `detect_screen()` to avoid background-button confusion on the mandatory race screen.

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