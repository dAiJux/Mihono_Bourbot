# Template Capture Guide

Templates are small PNG images of UI elements used for template matching (`cv2.matchTemplate`). They must be captured from your own game window to match your resolution and scale.

---

## Quick Start

```bash
python capture_templates.py
```

1. Select the game window
2. For each element: press **C**, type the name, draw a tight rectangle
3. Press **Enter** to save

All templates are saved to `templates/` at the project root.

---

## Required Templates

### Main Screen

| Name | What to capture |
|------|----------------|
| `btn_training` | "Training" button (capture bottom 50%, character overlaps top) |
| `btn_rest` | "Rest" button |
| `btn_recreation` | "Recreation" button |
| `btn_races` | Text "Races" only — tight crop, no character |
| `btn_rest_summer` | "Rest" button during summer break |
| `btn_infirmary` | Infirmary button when lit (injury present) or not lit |
| `btn_skills` | "Skills" button |

> **`btn_races` note:** Capture only the text label at the bottom of the button, not the character icon above it. A tight text-only crop gives much higher matching confidence (0.98+) vs a full-button crop with character overlay (0.47).

### Training Screen

| Name | What to capture |
|------|----------------|
| `training_speed` | Speed training icon |
| `training_stamina` | Stamina training icon |
| `training_power` | Power training icon |
| `training_guts` | Guts training icon |
| `training_wit` | Wit training icon |
| `training_selected` | Highlighted training slot indicator |
| `rainbow_training` | Rainbow glow effect on a training slot |
| `blue_burst` | Blue burst indicator |
| `spirit_burst` | White/spirit burst indicator |
| `friend_bar_partial` | Support bar (partially filled) |
| `friend_bar_orange` | Support bar (orange, near max) |
| `friend_bar_max` | Support bar (fully maxed) |
| `friend_bar_burst` | Support bar (burst active) |
| `type_speed` | Speed card type icon |
| `type_stamina` | Stamina card type icon |
| `type_power` | Power card type icon |
| `type_guts` | Guts card type icon |
| `type_wit` | Wit card type icon |
| `type_pal` | Pal card type icon |

### Race Elements

| Name | What to capture |
|------|----------------|
| `btn_race` | "Race" popup button (mandatory race day) |
| `btn_race_start` | "Race!" button (mandatory race screen) |
| `btn_race_start_ura` | "Race!" button (URA variant) |
| `btn_race_confirm` | Confirm button in race selection |
| `btn_race_launch` | Launch / Start Race button |
| `btn_race_next_finish` | "Next" / "Finish" button after race |
| `race_view_results_on` | "View Results" toggle ON |
| `race_view_results_off` | "View Results" toggle OFF |
| `btn_change_strategy` | "Change Strategy" button |
| `strategy_front` | "Front" strategy option |
| `strategy_pace` | "Pace" strategy option |
| `strategy_late` | "Late" strategy option |
| `strategy_end` | "End" strategy option |
| `target_race` | Target race indicator |
| `scheduled_race` | Scheduled race indicator |

### Event Elements

| Name | What to capture |
|------|----------------|
| `event_choice` | An event choice button (any one) |
| `event_scenario_window` | Scenario event banner/header |
| `event_trainee_window` | Trainee event banner/header |
| `event_support_window` | Support card event banner/header |

### Skill Screen

| Name | What to capture |
|------|----------------|
| `buy_skill` | The buy/purchase icon next to a skill |
| `learn_btn` | "Learn" button after selecting skills |
| `confirm_btn` | "Confirm" button on skill purchase |
| `gold_skill` | Gold skill rarity indicator |
| `white_skill` | White skill rarity indicator |

### Unity Cup

| Name | What to capture |
|------|----------------|
| `unity_training` | Unity training indicator |
| `btn_unity_launch` | "Launch" unity button |
| `btn_select_opponent` | "Select Opponent" button |
| `btn_begin_showdown` | "Begin Showdown" button |
| `btn_see_unity_results` | "See Results" button |
| `btn_next_unity` | "Next" button after unity match |
| `btn_launch_final_unity` | "Launch Final" button |
| `unity_opponent_card` | Opponent card in selection screen |
| `btn_claw_machine` | Claw machine button |

### Status Indicators

| Name | What to capture |
|------|----------------|
| `mood_great` | "Great" mood indicator |
| `mood_good` | "Good" mood indicator |
| `mood_normal` | "Normal" mood indicator |
| `mood_bad` | "Bad" mood indicator |
| `mood_awful` | "Awful" mood indicator |
| `energy_bar_full` | Energy bar (full) |
| `energy_bar_depleted` | Energy bar (empty/low) |

### Common / Navigation

| Name | What to capture |
|------|----------------|
| `btn_next` | "Next" button |
| `btn_tap` | "Tap to continue" / tap prompt |
| `btn_skip` | "Skip" button |
| `btn_ok` | "OK" button |
| `btn_close` | "Close" / X button |
| `btn_back` | "Back" / return button |
| `btn_confirm` | "Confirm" button |
| `btn_cancel` | "Cancel" button |
| `btn_try_again` | "Try Again" button |
| `btn_inspiration` | Inspiration button |
| `complete_career` | "Complete Career" screen indicator |

---

## Tips

### Tight crops beat wide crops

Exclude backgrounds, UI chrome, and especially character illustrations. The matching algorithm is sensitive to pixels that change between frames. For buttons where a character overlaps the top half, capture only the bottom portion containing the label.

### Resolution must match

Templates captured at 1920×1080 will not work reliably at 1280×720. Capture at the resolution you'll run the bot at and do not resize the game window afterward.

### Avoid animated areas

Character idles, scrolling text, and glowing effects change every frame. Capture only static parts of elements.

### Naming

Use exact lowercase names with underscores as listed above. The bot references these names directly in code.

### When to recapture

- After a game UI update
- After changing resolution or emulator
- When a previously working template suddenly fails

---

## Testing After Capture

```bash
python visual_debug.py
```

The live overlay shows which templates are detected on the current screen. Press **D** for the full diagnostics panel, which includes confidence scores and mask sweep results for each main screen button.