import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.vision import VisionModule
from scripts.models import GameScreen

with open("config/config.json") as f:
    config = json.load(f)

v = VisionModule(config)
v.find_game_window()
if not v.game_hwnd:
    print("Game window not found")
    sys.exit(1)

ALL_TEMPLATES = [
    ("buy_skill", 0.82), ("learn_btn", 0.72), ("confirm_btn", 0.72),
    ("training_speed", 0.60), ("training_stamina", 0.60), ("training_power", 0.60),
    ("training_guts", 0.60), ("training_wit", 0.60), ("white_burst", 0.65),
    ("btn_training", 0.80), ("btn_rest", 0.80), ("btn_recreation", 0.80),
    ("btn_races", 0.80), ("btn_rest_summer", 0.80), ("btn_skills", 0.80),
    ("btn_race", 0.80), ("btn_race_launch", 0.75), ("btn_race_confirm", 0.65),
    ("btn_race_start", 0.70), ("btn_race_start_ura", 0.70),
    ("btn_back", 0.80), ("btn_confirm", 0.80), ("btn_ok", 0.80),
    ("btn_next", 0.75), ("btn_tap", 0.75), ("btn_skip", 0.75),
    ("btn_try_again", 0.75), ("btn_close", 0.75), ("btn_cancel", 0.75),
    ("recreation_popup", 0.80), ("btn_claw_machine", 0.72),
    ("btn_inspiration", 0.70), ("btn_unity_launch", 0.75),
    ("btn_select_opponent", 0.75), ("btn_begin_showdown", 0.75),
    ("btn_race_next_finish", 0.75), ("complete_career", 0.90),
    ("event_scenario_window", 0.82), ("event_trainee_window", 0.82),
    ("event_support_window", 0.82),
    ("race_view_results_on", 0.70), ("race_view_results_off", 0.65),
    ("btn_change_strategy", 0.70),
    ("strategy_end", 0.80), ("strategy_late", 0.80),
    ("strategy_pace", 0.80), ("strategy_front", 0.80),
]

def run_test():
    ss = v.take_screenshot()
    platform = config.get("platform", "google_play")
    gx, gy, gw, gh = v.get_game_rect(ss)
    screen = v.detect_screen(ss)

    print(f"\n{'='*60}")
    print(f"  PAGE DETECTEE : {screen.name}")
    print(f"  Plateforme : {platform}  |  Zone de jeu : {gw}x{gh}")
    print(f"{'='*60}")

    _ENERGY_SCREENS = (GameScreen.MAIN, GameScreen.TRAINING, GameScreen.EVENT,
                       GameScreen.RACE_SELECT, GameScreen.INSUFFICIENT_FANS,
                       GameScreen.SCHEDULED_RACE_POPUP, GameScreen.SKILL_SELECT)
    if screen in _ENERGY_SCREENS:
        try:
            energy = v.read_energy_percentage(ss)
            mood = v.detect_mood(ss)
            print(f"\n  Energie : {energy:.0f}%  |  Humeur : {mood}")
        except Exception:
            pass

    if screen in (GameScreen.MAIN, GameScreen.TRAINING, GameScreen.RACE_SELECT):
        try:
            date = v.read_game_date(ss)
            if date:
                d = f"{date.get('year','')} {date.get('half','')} {date.get('month','')}".strip()
                if date.get("turn"):
                    d += f" (tour {date['turn']})"
                print(f"  Date : {d}")
        except Exception:
            pass

    if screen in (GameScreen.MAIN, GameScreen.TRAINING):
        try:
            stats = v.read_all_stats(ss)
            parts = [f"{k}={val}" for k, val in stats.items() if val > 0]
            if parts:
                print(f"  Stats : {', '.join(parts)}")
        except Exception:
            pass

    if screen == GameScreen.TRAINING:
        print(f"\n  --- Details entrainement ---")
        opts = v.get_training_options(ss)
        for name, pos in opts.items():
            status = f"position ({pos[0]},{pos[1]})" if pos else "non visible"
            print(f"    {name:12s} : {status}")
        try:
            chars = v.count_characters_per_training(ss)
            for name, count in chars.items():
                if count > 0:
                    print(f"    {name:12s} : {count} personnage(s)")
        except Exception:
            pass
        try:
            bursts = v.get_burst_status(ss)
            for btype, positions in bursts.items():
                if positions:
                    print(f"    Burst {btype} : {len(positions)} detecte(s)")
        except Exception:
            pass
        try:
            friendship = v._count_support_bars(ss)
            for ftype, count in friendship.items():
                if count > 0:
                    print(f"    Amitie {ftype} : {count}")
        except Exception:
            pass

    if screen == GameScreen.SKILL_SELECT:
        print(f"\n  --- Details skills ---")
        try:
            buy_icons = v.find_all_template("buy_skill", ss, 0.82, min_distance=20)
            visible = [(bx, by) for bx, by in buy_icons
                       if gy + int(gh * 0.20) < by < gy + int(gh * 0.95)]
            print(f"    {len(visible)} skill(s) visible(s)")
        except Exception:
            pass
        for btn, thr, label in [("learn_btn", 0.72, "Bouton apprendre"), ("confirm_btn", 0.72, "Bouton confirmer")]:
            pos, conf = v.find_template_conf(btn, ss, thr)
            if pos:
                print(f"    {label} : detecte ({conf*100:.0f}%)")

    if screen == GameScreen.EVENT:
        print(f"\n  --- Details evenement ---")
        try:
            title = v.read_event_title(ss)
            if title:
                print(f"    Titre : {title}")
        except Exception:
            pass
        etype = v.detect_event_type(ss)
        if etype:
            print(f"    Type : {etype}")

    if screen in (GameScreen.RACE_SELECT, GameScreen.RACE, GameScreen.RACE_START):
        print(f"\n  --- Details course ---")
        for tpl, thr, label in [
            ("btn_race", 0.80, "Bouton course"),
            ("btn_race_launch", 0.75, "Lancer course"),
            ("btn_race_start", 0.70, "Demarrer course"),
            ("btn_race_confirm", 0.65, "Confirmer course"),
            ("btn_change_strategy", 0.70, "Changer strategie"),
        ]:
            pos, conf = v.find_template_conf(tpl, ss, thr)
            if pos:
                print(f"    {label} : detecte ({conf*100:.0f}%)")

    print(f"\n  --- Tous les templates detectes ---")
    found_any = False
    for tpl, thr in ALL_TEMPLATES:
        pos, conf = v.find_template_conf(tpl, ss, thr)
        if pos:
            print(f"    {tpl:30s} : {conf*100:.0f}% (seuil: {thr*100:.0f}%)")
            found_any = True
        elif conf > 0.5:
            print(f"    {tpl:30s} : {conf*100:.0f}% < seuil {thr*100:.0f}% (pas detecte)")
            found_any = True
    if not found_any:
        print(f"    Aucun template ne matche !")
    print()

run_test()
