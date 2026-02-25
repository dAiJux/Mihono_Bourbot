# Changelog

All notable changes are documented here.

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