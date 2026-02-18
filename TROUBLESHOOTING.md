# Troubleshooting Guide

## Common Issues

### 1. "Game window not found"

**Symptoms:**
```
ERROR - Game window not found
```

**Causes & Fixes:**

| Cause | Fix |
|-------|-----|
| Game minimized | Restore window to visible state |
| Wrong window title | Add custom title to `VisionModule.GAME_WINDOW_TITLES` |
| Game not running | Start game first |

**Supported window titles:**
- `umamusume`
- `ウマ娘` (Japanese)
- `pretty derby`
- `dmm`

**Add custom title:**
```python
# scripts/vision/__init__.py
GAME_WINDOW_TITLES = [
    "umamusume", "ウマ娘", "pretty derby", "dmm",
    "your_custom_emulator_title"  # Add here
]
```

---

### 2. Template matching finds nothing

**Symptoms:**
```
WARNING - Button 'btn_training' not found
```

**Diagnostic checklist:**

- [ ] Templates captured at **same resolution** as current game?
- [ ] Window size unchanged since capture?
- [ ] Templates exist in `templates/` folder?
- [ ] Using correct template names (lowercase, underscores)?

**Fixes:**

```bash
# 1. Recapture all templates at current resolution
python tools/capture_templates.py

# 2. Lower matching threshold
# Edit config/config.json:
{
  "template_match_threshold": 0.7  # was 0.8
}

# 3. Test with vision mode
python -m scripts --test
```

---

### 3. OCR reads wrong stat values

**Symptoms:**
```
INFO - Stats: Speed=O18, Stamina=12OO  # 'O' instead of '0'
```

**Causes:**
- Low resolution (< 1080p)
- Wrong font rendering
- Tesseract not properly installed

**Fixes:**

| Issue | Fix |
|-------|-----|
| Tesseract not found | Install from [here](https://github.com/UB-Mannheim/tesseract/wiki) |
| Low resolution | Use 1920×1080 (1080p) for best OCR accuracy |
| Wrong OCR config | Increase `ocr_confidence` in config.json |

**Verify Tesseract:**
```bash
tesseract --version
# Should output: tesseract 5.x.x
```

**Set Tesseract path (if needed):**
```python
# scripts/vision/ocr.py
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

---

### 4. Clicks don't register in game

**Symptoms:**
- Bot runs but game doesn't respond
- Clicks logged but no visible effect

**Cause:** `PostMessage` blocked by emulator/renderer.

**Solutions:**

| Emulator | Compatibility |
|----------|---------------|
| BlueStacks 5 | ✅ Works |
| LDPlayer | ✅ Works |
| MuMu | ✅ Works |
| Nox | ⚠️ Hit or miss |
| DMM Player | ✅ Works |

**Fallback (last resort):**
```python
# Switch to pyautogui (takes over mouse)
# scripts/automation/clicks.py
import pyautogui
pyautogui.click(x, y)
```

**Verify window handle:**
```python
# Check logs for:
INFO - Game window found: <window title>
```

---

### 5. Bot gets stuck in a loop

**Symptoms:**
- Repeats same action 10+ times
- Logs show same screen state repeatedly

**Debugging steps:**

```bash
# 1. Press F12 to emergency stop

# 2. Check last actions
cat logs/bot.log | tail -50

# 3. Enable debug screenshots
# Edit config/config.json:
{
  "screenshot_on_error": true
}

# 4. Take manual screenshot of stuck screen
# Compare to templates in templates/ folder
```

**Common causes:**

| Stuck State | Missing Template | Fix |
|-------------|------------------|-----|
| After race | `btn_race_next_finish` | Recapture template |
| Event screen | `event_choice` | Recapture event choice button |
| Unity Cup | `btn_next_unity` | Recapture unity flow buttons |

---

### 6. ImportError: No module named 'win32gui'

**Symptoms:**
```
ImportError: DLL load failed while importing win32gui
```

**Fixes:**

```bash
# 1. Reinstall pywin32
pip uninstall pywin32
pip install pywin32==306

# 2. Run post-install script
python Scripts\pywin32_postinstall.py -install

# 3. Verify
python -c "import win32gui; print('OK')"
```

**If still fails:**
```bash
# Use conda (if applicable)
conda install pywin32

# Or reinstall Python entirely
```

---

### 7. Bot trains wrong stat

**Symptoms:**
- Bot trains Power but Speed is highest priority

**Diagnostic:**

```bash
# Check config
cat config/config.json | grep stat_priority
# Expected: ["speed", "power", "stamina", "wit", "guts"]

# Check targets
cat config/config.json | grep training_targets
# Expected: {"speed": 1200, "power": 1100, ...}
```

**Logic:**
- Bot trains **first stat in priority list** that hasn't reached target
- If Speed = 1200 (target met), moves to next priority (Power)

**Fix:** Adjust priorities or targets in GUI or config.json

---

### 8. Bot can't handle a specific event

**Symptoms:**
```
WARNING - No optimal choice found for event: <event title>
INFO - Defaulting to choice 1
```

**Fixes:**

```bash
# 1. Add event to database manually
# Edit config/event_database.json

# 2. Or scrape updated database
python tools/scrape_events.py

# 3. Find event data on game8.co
# https://game8.co/games/Umamusume-Pretty-Derby
```

**Manual event entry example:**
```json
{
  "common_events": [
    {
      "title_pattern": "Training Together",
      "choice": 2,
      "reason": "+Stamina +Guts, best for long-distance"
    }
  ]
}
```

---

### 9. GUI won't launch

**Symptoms:**
```
ModuleNotFoundError: No module named 'tkinter'
```

**Cause:** Python installed without tkinter (rare on Windows).

**Fixes:**

```bash
# Windows: Reinstall Python with "tcl/tk" option checked

# Linux (if ever ported):
sudo apt-get install python3-tk

# Verify
python -c "import tkinter; print('OK')"
```

---

### 10. .exe build fails

**Symptoms:**
```
pyinstaller: command not found
```

**Fixes:**

```bash
# 1. Install PyInstaller
pip install pyinstaller

# 2. Verify
pyinstaller --version

# 3. Build
python tools/build_exe.py

# 4. Check output
ls dist/Mihono Bourbot/
```

**Common build issues:**

| Error | Fix |
|-------|-----|
| `ModuleNotFoundError` during .exe run | Add missing import to build_exe.py `hiddenimports` |
| .exe doesn't launch | Run from command line to see error |
| Missing files | Copy `config/`, `templates/` to .exe folder |

---

## Getting Help

### Before asking:

1. ✅ Check `logs/bot.log` for errors
2. ✅ Run vision test: `python -m scripts --test`
3. ✅ Verify templates exist and are correctly named
4. ✅ Review [FAQ.md](FAQ.md)

### Information to provide:

```
- Python version: `python --version`
- OS: Windows 10/11
- Game resolution: 1920×1080
- Emulator: BlueStacks 5 / DMM
- Error message: <paste from logs>
- Last action: <from logs>
- Screenshot: <if available>
```

---

## Debug Mode

Enable detailed logging:

```json
// config/config.json
{
  "debug_mode": true,
  "screenshot_on_error": true,
  "log_level": "DEBUG"
}
```

**Output:**
```
DEBUG - Template 'btn_training' found at (542, 789) with confidence 0.87
DEBUG - Click at client(542, 789) window(542, 789)
DEBUG - Waiting 1.2s before next action
```
