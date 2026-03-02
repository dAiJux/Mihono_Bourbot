import json
import os
import sys

if getattr(sys, 'frozen', False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(_BASE_DIR)

CONFIG_PATH = os.path.join("config", "config.json")

DEFAULT_CONFIG = {
    "display_settings": {
        "windowed_mode": True,
        "resolution": [1080, 1920],
        "calibration_on_start": True,
        "fullscreen_fallback": False,
    },
    "training_targets": {
        "speed": 600,
        "stamina": 600,
        "power": 600,
        "wit": 600,
        "guts": 600,
        "tolerance": 50,
    },
    "stat_priority": ["speed", "power", "stamina", "wit", "guts"],
    "race_strategy": {"default": "End", "force_race_insufficient_fans": True},
    "thresholds": {
        "energy_low": 40,
        "energy_training": 50,
        "rainbow_energy_min": 40,
        "mood_threshold": "Great",
    },
    "automation_settings": {
        "click_offset_range": [5, 15],
        "action_delay_min": 1.0,
        "action_delay_max": 3.0,
        "ocr_confidence": 0.75,
        "template_match_threshold": 0.8,
    },
    "safety_settings": {
        "emergency_stop_key": "F12",
        "screenshot_on_error": True,
        "logging_enabled": True,
    },
    "event_handling": {
        "unknown_event_choice": 1,
        "use_event_database": True,
        "learn_from_choices": False,
    },
    "scenario": "unity_cup",
    "platform": "google_play",
    "window_title": "",
    "skill_wishlist": [],
    "skill_check_interval": 8,
}

REQUIRED_TEMPLATES = [
    "btn_training",
    "btn_rest",
    "btn_rest_summer",
    "btn_races",
    "btn_race",
    "btn_race_launch",
    "btn_race_start_ura",
    "btn_recreation",
    "btn_infirmary",
    "btn_next",
    "btn_next_unity",
    "btn_skip",
    "btn_tap",
    "btn_confirm",
    "btn_close",
    "btn_back",
    "btn_ok",
    "btn_cancel",
    "btn_try_again",
    "btn_race_confirm",
    "btn_race_start",
    "btn_race_next_finish",
    "btn_change_strategy",
    "btn_inspiration",
    "btn_claw_machine",
    "btn_unity_launch",
    "btn_select_opponent",
    "btn_begin_showdown",
    "btn_see_unity_results",
    "btn_launch_final_unity",
    "strategy_front",
    "strategy_pace",
    "strategy_late",
    "strategy_end",
    "training_speed",
    "training_stamina",
    "training_power",
    "training_guts",
    "training_wit",
    "training_selected",
    "type_speed",
    "type_stamina",
    "type_power",
    "type_guts",
    "type_wit",
    "type_pal",
    "white_burst",
    "blue_burst",
    "event_scenario_window",
    "event_trainee_window",
    "event_support_window",
    "event_choice",
    "target_race",
    "scheduled_race",
    "scheduled_race_popup",
    "rainbow_training",
    "complete_career",
    "insufficient_fans",
    "race_view_results_on",
    "race_view_results_off",
    "unity_opponent_card",
    "energy_bar_full",
    "energy_bar_depleted",
    "friend_bar_partial",
    "friend_bar_orange",
    "friend_bar_max",
    "friend_bar_burst",
    "gold_skill",
    "white_skill",
    "mood_great",
    "mood_good",
    "mood_normal",
    "mood_bad",
    "mood_awful",
    "buy_skill",
    "btn_skills",
    "learn_btn",
    "confirm_btn",
]

if getattr(__import__("sys"), "frozen", False):
    LIBS_DIR = os.path.join(_BASE_DIR, "_internal")
else:
    LIBS_DIR = os.path.join(_BASE_DIR, "libs")
_PACKAGES_JSON = os.path.join(_BASE_DIR, "config", "packages.json")

def _load_required_packages():
    try:
        with open(_PACKAGES_JSON, "r", encoding="utf-8") as _f:
            return json.load(_f)
    except Exception:
        return {
            "cv2": "opencv-python-headless",
            "numpy": "numpy",
            "PIL": "Pillow",
            "win32gui": "pywin32",
            "keyboard": "keyboard",
        }

REQUIRED_PACKAGES = _load_required_packages()