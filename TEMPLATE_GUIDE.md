# Template Capture Guide

Templates are **small PNG images** of UI elements used for template matching (OpenCV `matchTemplate`). You must capture these from your own game window to match your resolution.

---

## Quick Start

```bash
python tools/capture_templates.py
```

1. Select game window
2. For each template below, press **C**, type name, draw tight rectangle
3. Press **Enter** to save (or **Esc** to cancel)

Templates auto-save to categorized folders.

---

## Required Templates

### Main Screen Buttons

| Name | What to Capture | Purpose |
|------|----------------|---------|
| `btn_training` | "Training" button | Navigate to training screen |
| `btn_races` | "Races" button | Navigate to races |
| `btn_rest` | "Rest" button | Execute rest action |
| `btn_recreation` | "Recreation / Outing" button | Execute recreation |
| `btn_infirmary_on` | "Infirmary" button (lit up) | Detect & use infirmary |
| `btn_infirmary_off` | "Infirmary" button (grayed out) | Distinguish injury state |
| `btn_races` | "Races" button with character | Open race menu |

### Training Screen

| Name | What to Capture | Purpose |
|------|----------------|---------|
| `training_speed` | Speed training icon | Identify training type |
| `training_stamina` | Stamina training icon | Identify training type |
| `training_power` | Power training icon | Identify training type |
| `training_guts` | Guts training icon | Identify training type |
| `training_wit` | Wit training icon | Identify training type |
| `icon_rainbow` | Rainbow glow effect | Detect rainbow training |
| `burst_blue` | Blue burst indicator | Count blue bursts |
| `burst_white` | White burst indicator | Count white bursts |
| `friend_bar_partial` | Friend bar (partially filled) | Friendship tracking |
| `friend_bar_max` | Friend bar (fully filled) | Maxed friendship |

### Race Elements

| Name | What to Capture | Purpose |
|------|----------------|---------|
| `btn_race` | "Race" popup button | Race day detection |
| `btn_race_confirm` | "Race" confirm button | Race selection |
| `btn_race_launch` | "Launch" / "Start Race" button | Start race |
| `btn_race_start` | "Race!" button with character | Race day button |
| `btn_race_next_finish` | "Next" / "Finish" after race | Advance results |
| `race_view_results_on` | "View Results" (ON) | Skip race animation |
| `race_view_results_off` | "View Results" (OFF) | Toggle results |
| `btn_change_strategy` | "Change Strategy" button | Open strategy menu |
| `strategy_front` | "Front" strategy | Select strategy |
| `strategy_pace` | "Pace" strategy | Select strategy |
| `strategy_late` | "Late" strategy | Select strategy |
| `strategy_end` | "End" strategy | Select strategy |

### Event Elements

| Name | What to Capture | Purpose |
|------|----------------|---------|
| `event_choice` | Event choice button (any) | Detect event choices |
| `event_scenario_window` | Scenario event banner | Identify event type |
| `event_trainee_window` | Trainee event banner | Identify event type |
| `event_support_window` | Support event banner | Identify event type |

### Unity Cup

| Name | What to Capture | Purpose |
|------|----------------|---------|
| `btn_unity_launch` | "Unity Launch" button | Start unity match |
| `btn_select_opponent` | "Select Opponent" | Choose opponent |
| `btn_begin_showdown` | "Begin Showdown" | Start final |
| `btn_see_unity_results` | "See Results" | View unity results |
| `btn_next_unity` | "Next" after unity match | Advance flow |
| `btn_launch_final_unity` | "Launch Final" | Final round |
| `unity_training` | Unity training indicator | Detect unity training |

### Common Elements

| Name | What to Capture | Purpose |
|------|----------------|---------|
| `btn_next` | "Next" button | Advance dialogs |
| `btn_tap` | "Tap to continue" | Advance text |
| `btn_skip` | "Skip" button | Skip animations |
| `btn_ok` | "OK" button | Confirm dialogs |
| `btn_close` | "Close" (X) button | Dismiss popups |
| `btn_back` | "Back" / "Return" button | Navigate back |
| `btn_confirm` | "Confirm" button | Confirm actions |
| `btn_cancel` | "Cancel" button | Cancel actions |
| `btn_try_again` | "Try Again" button | Restart failed action |
| `btn_inspiration` | "Inspiration" button | Dismiss inspiration |

---

## Tips

### Resolution Matters

**Problem:** Templates captured at 1080p won't work at 720p.  
**Solution:** Capture at the resolution you'll run the bot at.

### Tight Crops

**Problem:** Extra background reduces matching accuracy.  
**Solution:** Crop as tightly as possible around the element.

### Avoid Dynamic Areas

**Problem:** Character animations, scrolling text change every frame.  
**Solution:** Exclude these from templates (capture only static parts).

### Naming Convention

**Required:** Use exact lowercase names with underscores:
- ✅ `btn_training`, `icon_speed`
- ❌ `Training Button`, `speed icon`, `btn-training`

### When to Recapture

**Triggers:**
- Game update changes UI
- Switched resolution
- Switched emulator
- Template matching suddenly fails

---

## Template Organization

Templates are auto-organized by category:

```
templates/
├── main_screen/         # btn_training, btn_races, btn_rest, etc.
├── training/            # training_speed, icon_rainbow, burst_blue, etc.
├── race/                # btn_race_launch, strategy_front, etc.
├── events/              # event_choice, event_scenario_window, etc.
├── unity/               # btn_unity_launch, unity_training, etc.
├── status/              # mood indicators, energy bar (if needed)
└── common/              # btn_next, btn_skip, btn_ok, etc.
```

---

## Testing Templates

After capturing, run **Vision Test**:

```bash
# From GUI
Click "Vision Test" button

# From CLI
python -m scripts --test
```

**Expected output:**
```
Screen: MAIN
  btn_training: ✓ found at (x, y)
  btn_races: ✓ found at (x, y)
  btn_rest: ✓ found at (x, y)
  ...
```

---

## Troubleshooting

### Template not detected

**Fixes:**
1. ✅ Recapture with tighter crop
2. ✅ Lower `template_match_threshold` (config.json: 0.8 → 0.7)
3. ✅ Ensure window size unchanged since capture
4. ✅ Check template exists in correct folder

### Multiple false positives

**Fixes:**
1. ✅ Crop tighter (less background)
2. ✅ Increase `template_match_threshold` (0.7 → 0.8)
3. ✅ Capture more distinctive part of element

### Template works sometimes

**Cause:** Element appearance changes (hover states, animations).  
**Fix:** Capture the "default" state (no hover, no animation).

---

## Advanced: Manual Template Creation

If capture tool doesn't work, you can create templates manually:

1. Take full screenshot of game window
2. Open in image editor (Paint, GIMP, Photoshop)
3. Crop tight rectangle around element
4. Save as PNG in correct folder with correct name
5. Test with vision test mode
