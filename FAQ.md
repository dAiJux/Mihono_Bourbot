# Frequently Asked Questions

## General

### What is Mihono Bourbot?

An automation tool for **Umamusume Pretty Derby** training scenarios. It captures the game window, makes decisions via a priority tree, and sends clicks directly to the window—your mouse and keyboard remain free.

### What platforms are supported?

**Windows only**. The bot relies on `pywin32` (win32gui, PostMessage) which is Windows-specific. Linux/Mac are not supported.

### Will I get banned?

⚠️ **Use at your own risk.** Automation may violate the game's Terms of Service. The bot includes anti-detection measures (random offsets, variable delays), but there's always risk.

---

## Setup

### I don't have Tesseract installed

1. Download Windows installer: [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki)
2. Install to default path
3. Add to system PATH, or set path in code:
   ```python
   import pytesseract
   pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
   ```

### `pip install pywin32` fails

**Solutions:**
- Ensure you're on Windows
- Try specific version: `pip install pywin32==306`
- If using venv, activate it first
- Run: `python Scripts\pywin32_postinstall.py -install`

### "Game window not found"

**Checklist:**
- ✅ Game running and **visible** (not minimized)
- ✅ Window title contains: `umamusume`, `ウマ娘`, `pretty derby`, or `dmm`
- ✅ For custom emulator titles, add to `VisionModule.GAME_WINDOW_TITLES`

---

## Templates

### What are templates?

Small PNG screenshots of UI elements (buttons, icons) used for template matching via OpenCV `matchTemplate`.

### How do I capture them?

```bash
python tools/capture_templates.py
```

1. Select game window
2. For each element, press **C**, type name, draw rectangle
3. Press **Enter** to save (or **C** to cancel)

See [TEMPLATE_GUIDE.md](TEMPLATE_GUIDE.md) for the complete list.

### Template matching is unreliable

**Fixes:**
- ✅ Re-capture at current resolution
- ✅ Lower `template_match_threshold` in config (0.8 → 0.7)
- ✅ Ensure window size unchanged since capture
- ✅ Crop tightly around elements (no extra background)

---

## Running

### Can I use my PC while the bot runs?

**Yes!** The bot uses `PostMessage` (not `pyautogui`), so your mouse and keyboard stay free.

### How do I stop the bot?

- Press **F12** (or your configured emergency stop key)
- Click **■ Stop Bot** in GUI
- Close the GUI window

### The bot keeps resting instead of training

**Cause:** Energy threshold too high.

**Fix:** Lower `thresholds.energy_training` in `config/config.json` (e.g., 40 → 30).

### The bot doesn't handle an event correctly

**Solutions:**
1. Add event to `config/event_database.json`
2. Find event data on [game8.co](https://game8.co/games/Umamusume-Pretty-Derby)
3. Re-run scraper: `python tools/scrape_events.py`

---

## Technical Issues

### Tesseract not found

**Error:**
```
TesseractNotFoundError: tesseract is not installed or it's not in your PATH
```

**Fix:**
1. Download from [here](https://github.com/UB-Mannheim/tesseract/wiki)
2. Install (default path recommended)
3. Verify: `tesseract --version`

### OCR reads wrong stat values

**Fixes:**
- ✅ Verify Tesseract installed
- ✅ Use 1080p resolution (720p less reliable)
- ✅ Increase `ocr_confidence` in config
- ✅ Check stat region coordinates for your resolution

### Clicks don't register in game

**Cause:** Some emulators block `PostMessage`.

**Solutions:**
- Try different emulator (BlueStacks, LDPlayer, MuMu, Nox)
- Verify window handle in logs
- Last resort: Switch to `pyautogui` (takes over mouse)

### Bot gets stuck in a loop

**Debugging:**
1. Press **F12** to stop
2. Check `logs/bot.log` for last actions
3. Verify all required templates exist
4. Take screenshot of stuck screen
5. Compare screenshot to templates

### `ImportError` when importing `win32gui`

**Fix:**
```bash
pip install pywin32
python -c "import win32gui; print('OK')"
```

If still fails:
```bash
pip install pywin32==306
python Scripts\pywin32_postinstall.py -install
```

### The bot trains the wrong stat

**Cause:** Misconfigured priorities or targets.

**Fix:**
1. Open GUI
2. Check **Stat Priority** list order
3. Verify `training_targets` in `config/config.json`
4. Bot trains first stat in list that hasn't hit target

---

## Building & Distribution

### How do I build a standalone .exe?

```bash
pip install pyinstaller
python tools/build_exe.py
```

Output: `dist/Mihono Bourbot/Mihono Bourbot.exe` (~80MB)

### The .exe is huge

**Explanation:** PyInstaller bundles Python interpreter + all dependencies.

**Options:**
- Use `--onedir` instead of `--onefile` for smaller main executable (with support folder)
- Remove unused dependencies from `requirements.txt`
- Expected size: 50-100 MB

---

## Getting More Help

1. ✅ Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
2. ✅ Review `logs/bot.log` for detailed action logs
3. ✅ Enable `screenshot_on_error` in config
4. ✅ Run vision test: `python -m scripts --test`
