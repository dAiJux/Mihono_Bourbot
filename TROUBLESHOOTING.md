# Troubleshooting Guide

---

## 1. "Game window not found"

**Symptoms:** `ERROR — Game window not found`

| Cause | Fix |
|-------|-----|
| Game minimized | Restore to visible state |
| Window not selected | Use the **Window** tab in the GUI to pick the game window |
| Game not running | Start the game first |

The **Window** tab lists all visible windows and lets you select the one running the game. This works with any emulator or player. If no window is selected, auto-detect looks for titles containing: `umamusume`, `ウマ娘`, `pretty derby`, `dmm`.

---

## 2. Template not detected / low confidence

**Symptoms:** `WARNING — Button 'btn_X' not found`

**Diagnostic:**
```bash
python visual_debug.py
# Navigate to the relevant screen, press D
```

The diagnostics panel shows confidence scores for each template. Buttons with character overlays (e.g. `btn_training`, `btn_recreation`) display a mask sweep — check which mask percentage yields the highest score.

**Common fixes:**

| Problem | Fix |
|---------|-----|
| Character overlaps template | Capture only the label/icon portion (bottom of button) |
| Resolution changed | Recapture all templates at current resolution |
| Window resized since capture | Keep window size fixed |
| Threshold too strict | Lower `template_match_threshold` in `config.json` (0.8 → 0.7) |

**`btn_races` specifically:** The full button includes a character illustration that drastically reduces confidence. Capture only the "Races" text label — expect 0.98+ confidence.

---

## 3. Screen detected incorrectly

**Symptoms:** Bot acts as if it is on the wrong screen (e.g. attempts Training during a mandatory race)

**Detection order** in `detect_screen()`:

1. Strategy popup
2. Skill select
3. **Race / mandatory race** (`btn_race_start`) ← checked first to avoid background button confusion
4. Race select
5. Main screen
6. Training
7. Others

**Common misdetections:**

| Actual screen | Detected as | Cause | Fix |
|---------------|-------------|-------|-----|
| Mandatory race | MAIN | Background buttons visible, `btn_race_start` threshold too high | Fixed in v1.1.0 |
| Strategy popup | SKILL_SELECT | `confirm_btn` matches strategy confirm button | Fixed in v1.1.0 |
| Race result (tap) | UNKNOWN | `btn_tap` threshold 0.75 > actual confidence | Fixed in v1.1.0 |

If you still see UNKNOWN on a screen, run `visual_debug.py` with **D** and check which templates are found.

---

## 4. OCR reads wrong stat values

**Symptoms:** `Stats: Speed=O18` — letters instead of digits

| Cause | Fix |
|-------|-----|
| EasyOCR not installed | `pip install easyocr` |
| Models not downloaded | Run once with internet connection (downloads ~500 MB) |
| Resolution very small | Use a larger game window — templates auto-scale but very small sizes reduce accuracy |

Verify: `python -c "import easyocr; print('OK')"`

---

## 5. Clicks don't register

**Symptoms:** Bot logs actions but game does not respond

`PostMessage` is blocked by some renderers.

| Emulator | Status |
|----------|--------|
| BlueStacks 5 | ✅ |
| LDPlayer | ✅ |
| MuMu | ✅ |
| DMM Player | ✅ |
| Nox | ⚠️ Inconsistent |

Verify the window handle is found: check logs for `Game window found: <title>`.

---

## 6. Skill screen issues

**Bot doesn't scroll skills:**
- Ensure the drag start Y is within the scrollable area (not on a button). The bot drags from 65% to 45% of screen height.
- Increase `time.sleep` after scroll if the list needs more time to settle.

**Bot scrolls past end of list:**
- End detection compares `buy_skill` icon positions between frames. If icons are detected inconsistently, disable OCR between scrolls by checking logs for icon count per scroll.

**Wrong skill names read:**
- Run `visual_debug.py` on the skill screen and check OCR output in the info panel.
- Gradient threshold is 2.0 — if titles are still missed, check scan window height (currently 10% of screen).

**Bot keeps scrolling after reaching the bottom:**
- Requires the same icon positions to appear in 2 consecutive frames. If animations shift icons slightly, increase the position tolerance or the stable_count threshold.

---

## 7. Bot gets stuck in a loop

**Symptoms:** Repeats same action indefinitely

**Debugging steps:**

1. Press **F12** to stop
2. Check `logs/bot.log` — look for the last action and screen state
3. Enable debug screenshots in `config.json`: `"screenshot_on_error": true`
4. Run `python visual_debug.py` on the stuck screen

**Common causes:**

| Stuck on | Missing template | Fix |
|----------|-----------------|-----|
| After race | `btn_race_next_finish` / `btn_tap` | Recapture |
| Event screen | `event_choice` | Recapture |
| Unity Cup | `btn_next_unity` | Recapture |
| Skill screen | `learn_btn` / `confirm_btn` | Recapture |

---

## 8. Wrong training stat selected

The bot trains the first stat in priority order that has not reached its target (with tolerance). If all targets are met, it continues training non-maxed stats.

**Check:**
```bash
# config/config.json
"stat_priority": ["speed", "power", "stamina", "wit", "guts"]
"training_targets": {"speed": 1200, "power": 1100, ...}
```

Adjust priorities and targets in the GUI or directly in `config.json`.

---

## 9. ImportError: win32gui

```bash
pip uninstall pywin32
pip install pywin32==306
python Scripts\pywin32_postinstall.py -install
python -c "import win32gui; print('OK')"
```

---

## 10. .exe build fails

```bash
pip install pyinstaller
python build_exe.py
```

After building, copy `config/` and `templates/` into the `dist/Mihono Bourbot/` folder — the exe does not bundle them automatically.

| Error | Fix |
|-------|-----|
| `ModuleNotFoundError` at runtime | Add module to `hiddenimports` in `build_exe.py` |
| exe does not launch | Run from a terminal to see the full error |
| Missing config / templates | Copy folders manually to the dist directory |

---

## Debug Mode

```json
// config/config.json
{
  "debug_mode": true,
  "screenshot_on_error": true
}
```

Use `python visual_debug.py` for a live annotated view of what the bot currently detects. Press **D** for the full diagnostics panel.