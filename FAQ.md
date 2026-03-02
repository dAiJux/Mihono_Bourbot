# FAQ

## General

### What is Mihono Bourbot?

An automation bot for **Umamusume Pretty Derby** training scenarios. It captures the game window, makes decisions via a priority tree, and sends clicks directly to the window — your mouse and keyboard stay free.

### What platforms are supported?

**Windows only.** The bot relies on `pywin32` (`PostMessage`, `PrintWindow`) which are Windows-specific APIs.

### Will I get banned?

⚠️ Use at your own risk. Automation may violate the game's Terms of Service. The bot includes anti-detection measures (random offsets, variable delays) but there is always risk.

---

## Setup

### How do I install dependencies?

```bash
pip install -r requirements.txt
```

EasyOCR downloads language models (~500 MB) on first use. An internet connection is required the first time.

### `pip install pywin32` fails

```bash
pip install pywin32==306
python Scripts\pywin32_postinstall.py -install
```

### "Game window not found"

- Game must be running and **visible** (not minimized)
- Use the **Window** tab in the GUI to manually select the game window — this works with any emulator or player
- If no window is selected, auto-detect uses these title keywords: `umamusume`, `ウマ娘`, `pretty derby`, `dmm`

---

## Templates

### What are templates?

Small PNG screenshots of UI elements matched against the live screen using OpenCV `matchTemplate`.

### How do I capture them?

```bash
python capture_templates.py
```

See [TEMPLATE_GUIDE.md](TEMPLATE_GUIDE.md) for the full list and capture tips.

### A template is not detected

1. Re-capture with a tighter crop (less background)
2. Ensure game window size has not changed since capture
3. Run `python visual_debug.py` and press **D** to see confidence scores
4. Lower the threshold in `config.json` (`template_match_threshold`: 0.8 → 0.7) if needed

### `btn_races` is not detected

Use a tight crop of the "Races" text label only — exclude the character illustration above it. A text-only crop achieves 0.98+ confidence; a full-button crop with character overlay scores around 0.47 and fails detection.

---

## Running

### Can I use my PC while the bot runs?

Yes. `PostMessage` sends clicks directly to the window handle — your mouse does not move.

### How do I stop the bot?

- Press **F12** (or the configured emergency stop key)
- Click **■ Stop** in the GUI
- Close the GUI window

### The bot gets stuck after a race

Check that `btn_race_next_finish` and `btn_tap` templates exist. These are used to advance race result screens. If missing or inaccurate, the bot cannot exit the result flow.

### The bot misidentifies the mandatory race screen as Main or Training

This is a known issue when background buttons are visible behind the race overlay. It is resolved in v1.1.0: `btn_race_start` is now checked at the top of `detect_screen`, before any main/training button checks.

### The bot keeps resting instead of training

Energy threshold is too high. Lower `thresholds.energy_training` in `config/config.json` (e.g. 40 → 30).

### The bot doesn't handle a specific event

1. Find the event on [game8.co](https://game8.co/games/Umamusume-Pretty-Derby)
2. Add it to `config/event_database.json`, or run `python scrape_events.py` to pull updated data

### Skill buying doesn't work

- Ensure `buy_skill`, `learn_btn`, and `confirm_btn` templates are captured
- Check `skill_wishlist` in `config.json` — names must loosely match what OCR reads
- Run `visual_debug.py` on the skill screen and press **D** to see what is detected

---

## Technical Issues

### OCR reads wrong stat values

- Templates auto-scale to any resolution, but very small windows may reduce OCR accuracy
- Verify EasyOCR: `python -c "import easyocr; print('OK')"`
- Models must have been downloaded (requires internet on first run)

### Clicks don't register in game

Some emulators block `PostMessage`. Recommended emulators: BlueStacks 5, LDPlayer, MuMu, DMM Player.

### Screen detected as UNKNOWN

Run `python visual_debug.py`, navigate to the problematic screen, and press **D**. The diagnostics panel shows which templates were found and their confidence scores. Recapture any missing or low-confidence templates.

### ImportError: No module named 'win32gui'

```bash
pip uninstall pywin32
pip install pywin32==306
python Scripts\pywin32_postinstall.py -install
```

---

## Building

### How do I build a standalone .exe?

```bash
pip install pyinstaller
python build_exe.py
```

Output: `dist/Mihono Bourbot/Mihono Bourbot.exe`

The `.exe` folder must also contain `config/` and `templates/` to run correctly.