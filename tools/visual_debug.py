import cv2
import numpy as np
import json
import sys
import os
import time
import argparse
from pathlib import Path
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.vision import VisionModule
from scripts.models import GameScreen

WINDOW_NAME = "Visual Debug"

COLORS = {
    "rainbow":        (0, 215, 255),
    "white_burst":    (255, 255, 255),
    "blue_burst":     (255, 180, 0),
    "bar_blue":       (255, 180, 0),
    "bar_green":      (0, 255, 128),
    "bar_orange":     (0, 165, 255),
    "bar_gold":       (0, 255, 255),
    "bar_empty":      (128, 128, 128),
    "event_choice":   (255, 0, 255),
    "button":         (128, 255, 128),
    "training_icon":  (255, 200, 0),
    "column":         (100, 100, 100),
    "energy_bar":     (0, 200, 255),
    "game_rect":      (255, 255, 0),
    "roi":            (180, 180, 60),
    "mood":           (255, 128, 0),
    "event_window":   (200, 100, 255),
    "warning":        (0, 0, 255),
}

TRAINING_DETECT_DEFS = [
    ("burst_white",       "white_burst",    0.70),
    ("burst_blue",        "blue_burst",     0.70),
    ("icon_rainbow",      "rainbow",        0.75),
]


TRAINING_ICONS = [
    "training_speed", "training_stamina", "training_power",
    "training_guts", "training_wit",
]

MAIN_BUTTONS = [
    "btn_training", "btn_rest", "btn_recreation", "btn_races",
    "btn_rest_summer", "btn_skills",
]

GENERIC_BUTTONS = [
    "btn_confirm", "btn_ok", "btn_close", "btn_cancel",
    "btn_skip", "btn_tap", "btn_next", "btn_back",
    "btn_race_start", "btn_race_next_finish",
    "btn_inspiration", "btn_claw_machine", "btn_unity_launch",
]

EVENT_WINDOWS = [
    "event_scenario_window", "event_trainee_window", "event_support_window",
]

def _put_label(img, text, x, y, color, scale=0.55, thickness=1):
    """Draw text with a dark background pill for readability."""
    font = cv2.FONT_HERSHEY_SIMPLEX
    (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)
    pad = 3
    bx1 = x - pad
    by1 = y - th - pad
    bx2 = x + tw + pad
    by2 = y + baseline + pad
    sub = img[max(0, by1):min(img.shape[0], by2), max(0, bx1):min(img.shape[1], bx2)]
    if sub.size > 0:
        dark = (sub * 0.3).astype(np.uint8)
        img[max(0, by1):min(img.shape[0], by2), max(0, bx1):min(img.shape[1], bx2)] = dark
    cv2.putText(img, text, (x, y), font, scale, color, thickness, cv2.LINE_AA)

class VisualDebugTool:

    def __init__(self, config_path=os.path.join("config", "config.json"), screenshot_path=None):
        with open(config_path) as f:
            self.config = json.load(f)
        self.vision = VisionModule(self.config)
        self.screenshot_path = screenshot_path
        self.screenshot = None
        self.overlay = None
        self.detections = []
        self.mode = "all"
        self.show_rois = False
        self.threshold_offset = 0.0
        self.screen = GameScreen.UNKNOWN
        self.info_lines = []

    def take_or_load_screenshot(self):
        if self.screenshot_path:
            img = cv2.imread(self.screenshot_path)
            if img is None:
                print(f"ERROR: Cannot load {self.screenshot_path}")
                sys.exit(1)
            self.screenshot = img
        else:
            self.vision.find_game_window()
            if not self.vision.game_hwnd:
                print("ERROR: Game window not found!")
                sys.exit(1)
            self.screenshot = self.vision.take_screenshot()
        Path("logs/debug").mkdir(parents=True, exist_ok=True)
        cv2.imwrite("logs/debug/visual_debug_raw.png", self.screenshot)
        h, w = self.screenshot.shape[:2]
        print(f"Screenshot captured: {w}x{h}")

    def detect_all(self):
        self.detections = []
        self.info_lines = []
        ss = self.screenshot
        gx, gy, gw, gh = self.vision.get_game_rect(ss)

        self.screen = self.vision.detect_screen(ss)
        self.info_lines.append(f"Screen: {self.screen.value.upper()}")
        self.info_lines.append(f"Game area: ({gx},{gy}) {gw}x{gh}")

        _DATE_SCREENS = (GameScreen.MAIN, GameScreen.RACE_SELECT, GameScreen.RACE)
        if self.screen in _DATE_SCREENS:
            game_date = self.vision.read_game_date(ss)
            if game_date:
                date_str = f"{game_date.get('year','')} {game_date.get('half','')} {game_date.get('month','')}".strip()
                if game_date.get('turn'):
                    date_str += f" (turn {game_date['turn']})"
                self.info_lines.append(f"Date: {date_str}")
            else:
                self.info_lines.append("Date: unreadable")

        self.detections.append(dict(
            type="rect", label="game_rect", color=COLORS["game_rect"],
            x1=gx, y1=gy, x2=gx+gw, y2=gy+gh, cat="frame"))

        if self.screen in (GameScreen.MAIN, GameScreen.TRAINING, GameScreen.EVENT,
                         GameScreen.RACE_SELECT):
            self._detect_energy(ss, gx, gy, gw, gh)
            self._detect_mood(ss)
            self._detect_stats(ss)

        if self.screen in (GameScreen.MAIN, GameScreen.UNKNOWN):
            self._detect_buttons(ss, gx, gw, MAIN_BUTTONS, "main_btn")
            self._detect_infirmary(ss, gx, gw)
            self._detect_friendship_bars(ss)

        if self.screen in (GameScreen.TRAINING, GameScreen.UNKNOWN):
            self._detect_training_items(ss, gx, gy, gw, gh)
            self._detect_training_columns(ss, gx, gy, gw, gh)

        if self.screen in (GameScreen.EVENT, GameScreen.UNKNOWN):
            self._detect_events(ss, gx, gy, gw, gh)

        if self.screen in (GameScreen.RACE_SELECT, GameScreen.UNKNOWN):
            self._detect_race_select(ss, gx, gy, gw, gh)

        if self.screen in (GameScreen.RACE, GameScreen.UNKNOWN):
            self._detect_race_prep(ss, gx, gy, gw, gh)

        if self.screen in (GameScreen.STRATEGY, GameScreen.UNKNOWN):
            self._detect_strategy_popup(ss, gx, gy, gw, gh)

        if self.screen in (GameScreen.RECREATION, GameScreen.UNKNOWN):
            self._detect_pal_recreation_popup(ss, gx, gy, gw, gh)

        if self.screen in (GameScreen.UNITY, GameScreen.UNKNOWN):
            self._detect_unity_screen(ss, gx, gy, gw, gh)

        if self.screen in (GameScreen.SKILL_SELECT, GameScreen.UNKNOWN):
            self._detect_skills_screen(ss, gx, gy, gw, gh)

        if self.screen == GameScreen.INSPIRATION:
            pos = self.vision.find_template("btn_inspiration", ss, 0.70)
            if pos:
                self.detections.append(dict(
                    type="point", label="inspiration",
                    color=(0, 215, 255), x=pos[0], y=pos[1], cat="button"))
                self.info_lines.append(f"btn_inspiration: {pos}")

        if self.screen == GameScreen.CAREER_COMPLETE:
            for tpl in ["complete_career"]:
                pos = self.vision.find_template(tpl, ss, 0.75)
                if pos:
                    self.detections.append(dict(
                        type="point", label=tpl, color=(0, 200, 255),
                        x=pos[0], y=pos[1], cat="career"))
                    self.info_lines.append(f"  {tpl}: {pos}")

        if self.screen != GameScreen.SKILL_SELECT:
            self._detect_buttons(ss, gx, gw, GENERIC_BUTTONS, "gen_btn")

        if self.show_rois:
            self._detect_calibrated_rois(ss, gx, gy, gw, gh)

    def _detect_energy(self, ss, gx, gy, gw, gh):
        energy = self.vision.read_energy_percentage(ss)
        self.info_lines.append(f"Energy: {energy:.0f}%")
        eb = self.vision._calibration.get("energy_bar", {})
        y1 = gy + int(gh * eb.get("y1", 0.082))
        y2 = gy + int(gh * eb.get("y2", 0.098))
        x1 = gx + int(gw * eb.get("x1", 0.33))
        x2 = gx + int(gw * eb.get("x2", 0.69))
        self.detections.append(dict(
            type="rect", label=f"Energy {energy:.0f}%",
            color=COLORS["energy_bar"],
            x1=x1, y1=y1, x2=x2, y2=y2, cat="energy"))

    def _detect_mood(self, ss):
        mood = self.vision.detect_mood(ss)
        self.info_lines.append(f"Mood: {mood}")
        if mood != "unknown":
            gx, gy, gw, gh = self.vision.get_game_rect(ss)
            cx = gx + int(gw * 0.80)
            cy = gy + int(gh * 0.125)
            self.detections.append(dict(
                type="point", label=f"mood: {mood}",
                color=COLORS["mood"], x=cx, y=cy, cat="mood"))

    def _detect_stats(self, ss):
        """Read and display the 5 main stats from the bottom bar."""
        stats = self.vision.read_stats(ss)
        if stats:
            parts = [f"{n[:3].title()}={stats[n]}" for n in self.vision.STAT_NAMES
                     if n in stats]
            self.info_lines.append(f"Stats: {' | '.join(parts)}")
        else:
            self.info_lines.append("Stats: unreadable")

    def _detect_training_items(self, ss, gx, gy, gw, gh):
        """Bursts, rainbow, support cards — only on TRAINING screen."""
        for tpl_name, label, base_t in TRAINING_DETECT_DEFS:
            t = max(0.3, base_t + self.threshold_offset)
            hits = self.vision.find_all_template(tpl_name, ss, t, min_distance=30)
            for px, py in hits:
                self.detections.append(dict(
                    type="point", label=label,
                    color=COLORS.get(label, (200, 200, 200)),
                    x=px, y=py, cat="train_detect"))
            if hits:
                self.info_lines.append(f"{label}: {len(hits)} → {hits}")

        bar_info = self.vision._count_support_bars(ss)
        sr = self.vision._calibration.get("support_region", {})
        if sr and bar_info["bars"]:
            sx1 = gx + int(gw * sr["x1"])
            sy1 = gy + int(gh * sr["y1"])
            sx2 = gx + int(gw * sr["x2"])
            for y_start, y_end, btype in bar_info["bars"]:
                band_color = COLORS.get(f"bar_{btype}", (200, 200, 200))
                label = f"bar:{btype}"
                self.detections.append(dict(
                    type="rect", label=label, color=band_color,
                    x1=sx1, y1=sy1 + y_start, x2=sx2, y2=sy1 + y_end,
                    cat="friendship"))
        self.info_lines.append(
            f"Support bars: {bar_info['total']} "
            f"({', '.join(t for _, _, t in bar_info['bars'])})"
        )

        card_types = self.vision.detect_card_types_with_pal(ss)
        abbrevs = {"speed": "Spe", "stamina": "Sta", "power": "Pow",
                   "guts": "Gut", "wit": "Wit", "pal": "PAL", "unknown": "?"}
        if card_types:
            ct_str = " | ".join(abbrevs.get(ct, ct) for ct in card_types)
            self.info_lines.append(f"Card types: {ct_str}")

        selected_training = self._detect_selected_training(ss, gx, gy, gw, gh)
        if selected_training:
            self.info_lines.append(f"Selected training: {selected_training}")
        else:
            self.info_lines.append("Selected training: unknown")

        if card_types and bar_info["bars"]:
            rainbow_count = 0
            bars = bar_info["bars"]
            icon_positions = self.vision._detect_type_icons(ss)
            rainbow_eligible = []
            for i, ctype in enumerate(card_types):
                if i < len(bars):
                    _, _, bcolor = bars[i]
                    is_orange = bcolor in ("orange", "gold")
                    matches_training = (
                        selected_training is not None
                        and ctype == selected_training
                    )
                    abbrev = abbrevs.get(ctype, ctype)
                    if ctype == "pal":
                        self.info_lines.append(
                            f"  card {i+1}: PAL ({bcolor}, no rainbow possible)"
                        )
                    elif is_orange and matches_training:
                        rainbow_count += 1
                        self.info_lines.append(
                            f"  >> RAINBOW card {i+1}: {abbrev} ({bcolor} + matches)"
                        )
                        if i < len(icon_positions):
                            sr2 = self.vision._calibration.get("support_region", {})
                            if sr2:
                                icon_y = icon_positions[i][0]
                                iy = gy + int(gh * sr2["y1"]) + icon_y
                                ix = gx + int(gw * sr2["x1"])
                                ix2 = gx + int(gw * sr2["x2"])
                                self.detections.append(dict(
                                    type="rect",
                                    label="RAINBOW",
                                    color=COLORS["rainbow"],
                                    x1=ix, y1=iy - 20,
                                    x2=ix2, y2=iy + 20,
                                    cat="rainbow"))
                    elif is_orange:
                        rainbow_eligible.append(ctype)
                        self.info_lines.append(
                            f"  card {i+1}: {abbrev} ({bcolor}, rainbow on {ctype} training)"
                        )
            if rainbow_count:
                self.info_lines.append(f"Rainbows active: {rainbow_count}")
            if rainbow_eligible and not rainbow_count:
                targets = ", ".join(abbrevs.get(t, t) for t in set(rainbow_eligible))
                self.info_lines.append(
                    f"  No rainbow here - would rainbow on: {targets}"
                )

        for tpl in TRAINING_ICONS:
            pos = self.vision.find_template(tpl, ss, 0.55)
            if pos:
                short = tpl.replace("training_", "")
                self.detections.append(dict(
                    type="point", label=short,
                    color=COLORS["training_icon"],
                    x=pos[0], y=pos[1], cat="train_icon"))
                self.info_lines.append(f"  icon {short} at {pos}")

        self._detect_friendship_bars(ss)
        levels = self.vision.count_support_friendship_leveled(ss)
        self.info_lines.append(
            f"Friendship: partial={levels['partial']} orange+={levels['orange_plus']}"
            f" pal_orange={levels['pal_orange']} pal={'yes' if levels['pal'] else 'no'}"
        )

    def _detect_selected_training(self, ss, gx, gy, gw, gh):
        """Detect which training column is currently selected.

        Uses the training_selected template to find the selection
        indicator, then matches its X position to the closest
        calibrated training column.
        """
        sel_pos = self.vision.find_template("training_selected", ss, 0.60)
        if not sel_pos:
            return None

        cal = self.vision._calibration
        best_stat = None
        best_dist = float("inf")
        for stat in ["speed", "stamina", "power", "guts", "wit"]:
            c = cal.get(f"train_{stat}")
            if c and "x" in c:
                cx = gx + int(gw * c["x"])
                dist = abs(sel_pos[0] - cx)
                if dist < best_dist:
                    best_dist = dist
                    best_stat = stat
        return best_stat

    def _detect_training_columns(self, ss, gx, gy, gw, gh):
        cal = self.vision._calibration
        centers = {}
        for s in ["speed", "stamina", "power", "guts", "wit"]:
            c = cal.get(f"train_{s}")
            if c and "x" in c:
                centers[s] = gx + int(gw * c["x"])
        if len(centers) < 3:
            return
        names = sorted(centers, key=centers.get)
        for i, n in enumerate(names):
            cx = centers[n]
            if i < len(names) - 1:
                bx = (cx + centers[names[i + 1]]) // 2
                self.detections.append(dict(
                    type="vline", label="", color=COLORS["column"],
                    x=bx, y1=gy, y2=gy + gh, cat="column"))
            cy = gy + int(gh * cal.get(f"train_{n}", {}).get("y", 0.843))
            self.detections.append(dict(
                type="point", label=n[:3].upper(),
                color=(255, 255, 255), x=cx, y=cy, cat="train_pos"))

    def _detect_friendship_bars(self, ss):
        bar_info = self.vision._count_support_bars(ss)
        sr = self.vision._calibration.get("support_region", {})
        if not sr or not bar_info["bars"]:
            return
        gx, gy, gw, gh = self.vision.get_game_rect(ss)
        sx1 = gx + int(gw * sr["x1"])
        sy1 = gy + int(gh * sr["y1"])
        sx2 = gx + int(gw * sr["x2"])
        for y_start, y_end, btype in bar_info["bars"]:
            band_color = COLORS.get(f"bar_{btype}", (200, 200, 200))
            self.detections.append(dict(
                type="rect", label=f"bar:{btype}", color=band_color,
                x1=sx1, y1=sy1 + y_start, x2=sx2, y2=sy1 + y_end,
                cat="friendship"))

    def _detect_infirmary(self, ss, gx, gw):
        best_label = None
        best_conf = 0
        best_pos = None
        for name in ["btn_infirmary"]:
            search, ox, oy = self.vision._get_search_area(name, ss)
            tpl = self.vision._get_scaled_template(name)
            if tpl is None or search.shape[0] < tpl.shape[0] or search.shape[1] < tpl.shape[1]:
                continue
            res = cv2.matchTemplate(search, tpl, cv2.TM_CCOEFF_NORMED)
            _, mv, _, ml = cv2.minMaxLoc(res)
            if mv > best_conf:
                best_conf = mv
                best_label = name.replace("btn_", "")
                best_pos = (ox + ml[0] + tpl.shape[1] // 2, oy + ml[1] + tpl.shape[0] // 2)
        if best_conf >= 0.55 and best_pos and gx <= best_pos[0] <= gx + gw:
            self.detections.append(dict(
                type="point", label=best_label, color=COLORS["button"],
                x=best_pos[0], y=best_pos[1], cat="main_btn"))
            self.info_lines.append(f"  {best_label}: {best_pos}")

    def _detect_buttons(self, ss, gx, gw, btn_list, cat):
        for btn in btn_list:
            pos = self.vision.find_template(btn, ss, 0.70)
            if pos and gx <= pos[0] <= gx + gw:
                short = btn.replace("btn_", "").replace("event_", "ev_")
                self.detections.append(dict(
                    type="point", label=short, color=COLORS["button"],
                    x=pos[0], y=pos[1], cat=cat))
                if cat == "main_btn":
                    self.info_lines.append(f"  {short}: {pos}")

    def _detect_race_select(self, ss, gx, gy, gw, gh):
        """Annotate race selection screen: Goal race and Race button."""
        goal = self.vision.detect_goal_race(ss)
        if goal:
            self.detections.append(dict(
                type="hline", label="GOAL", color=(0, 165, 255),
                y=goal[1], x1=gx, x2=gx + gw, cat="race_sel"))

        race_btn = self.vision.find_race_select_button(ss)
        if race_btn:
            self.detections.append(dict(
                type="point", label="Race btn", color=(0, 255, 0),
                x=race_btn[0], y=race_btn[1], cat="race_sel"))

    def _detect_race_prep(self, ss, gx, gy, gw, gh):
        """Annotate race preparation screen: View Results, Race, Strategy."""
        RACE_PREP_BTNS = [
            ("race_view_results_on", 0.85), ("race_view_results_off", 0.70),
            ("btn_race_start", 0.70), ("btn_race_start_ura", 0.70),
            ("btn_race_launch", 0.70),
            ("btn_change_strategy", 0.70), ("btn_skip", 0.70),
        ]
        for btn, thr in RACE_PREP_BTNS:
            pos = self.vision.find_template(btn, ss, thr)
            if pos:
                short = btn.replace("race_view_results_", "vr_").replace("btn_", "")
                self.detections.append(dict(
                    type="point", label=short, color=(0, 255, 0),
                    x=pos[0], y=pos[1], cat="race_prep"))
                self.info_lines.append(f"  {short}: {pos}")

    def _detect_pal_recreation_popup(self, ss, gx, gy, gw, gh):
        popup_pos = self.vision.find_template("recreation_popup", ss, 0.70)
        if not popup_pos:
            return

        self.detections.append(dict(
            type="point", label="rec_popup",
            color=(60, 220, 60), x=popup_pos[0], y=popup_pos[1], cat="pal_rec"))
        self.info_lines.append("PAL Recreation popup detected")

        empty_arrows = self.vision.find_all_template("arrow_empty", ss, 0.65, min_distance=15)
        filled_arrows = self.vision.find_all_template("arrow_filled", ss, 0.80, min_distance=15)

        EXCLUSION_DIST = 20
        filtered_empty = [
            ep for ep in empty_arrows
            if not any(abs(ep[0] - fp[0]) <= EXCLUSION_DIST and abs(ep[1] - fp[1]) <= EXCLUSION_DIST
                       for fp in filled_arrows)
        ]

        for pt in filtered_empty:
            self.detections.append(dict(
                type="point", label="arr_empty", color=(160, 160, 160),
                x=pt[0], y=pt[1], cat="pal_rec"))
        for pt in filled_arrows:
            self.detections.append(dict(
                type="point", label="arr_filled", color=(255, 160, 0),
                x=pt[0], y=pt[1], cat="pal_rec"))

        rows_with_empty = []
        if filtered_empty:
            sorted_e = sorted(filtered_empty, key=lambda p: p[1])
            cur = [sorted_e[0]]
            for pt in sorted_e[1:]:
                if abs(pt[1] - cur[-1][1]) <= 50:
                    cur.append(pt)
                else:
                    rows_with_empty.append(cur)
                    cur = [pt]
            rows_with_empty.append(cur)

        self.info_lines.append(
            f"  arrows empty={len(filtered_empty)} (raw={len(empty_arrows)})  "
            f"filled={len(filled_arrows)}  rows_available={len(rows_with_empty)}")

        for i, row in enumerate(rows_with_empty):
            avg_y = int(sum(p[1] for p in row) / len(row))
            color = (0, 220, 60) if i == 0 else (100, 200, 100)
            label = f"PAL row {i + 1}{' <- CLICK' if i == 0 else ''}"
            self.detections.append(dict(
                type="point", label=label, color=color, x=popup_pos[0], y=avg_y, cat="pal_rec"))
            self.info_lines.append(
                f"  row {i + 1}: {len(row)} empty arrow(s) y={avg_y}"
                + (" <- would click" if i == 0 else ""))

        trainee_pos = self.vision.find_template("trainee_uma", ss, 0.70)
        if trainee_pos:
            is_fallback = len(rows_with_empty) > 0
            label = "trainee_uma (fallback)" if is_fallback else "trainee_uma <- CLICK (all PAL done)"
            color = (60, 60, 220) if is_fallback else (0, 220, 60)
            self.detections.append(dict(
                type="point", label=label, color=color,
                x=trainee_pos[0], y=trainee_pos[1], cat="pal_rec"))
            self.info_lines.append(
                f"  trainee_uma: {trainee_pos}"
                + (" (fallback only)" if is_fallback else " <- would click"))
        else:
            self.info_lines.append("  trainee_uma: template MISSING ou non detecte")

    def _detect_strategy_popup(self, ss, gx, gy, gw, gh):
        """Annotate strategy popup: End, Late, Pace, Front + Confirm/Cancel."""
        STRAT_BTNS = ["strategy_end", "strategy_late", "strategy_pace", "strategy_front"]
        found_any = False
        for btn in STRAT_BTNS:
            pos = self.vision.find_template(btn, ss, 0.80)
            if pos:
                short = btn.replace("strategy_", "")
                self.detections.append(dict(
                    type="point", label=short, color=(255, 200, 0),
                    x=pos[0], y=pos[1], cat="strategy"))
                found_any = True
        if found_any:
            for btn in ["btn_confirm", "btn_cancel"]:
                pos = self.vision.find_template(btn, ss, 0.80)
                if pos:
                    short = btn.replace("btn_", "")
                    self.detections.append(dict(
                        type="point", label=short, color=(0, 255, 0),
                        x=pos[0], y=pos[1], cat="strategy"))
            self.info_lines.append("Strategy popup detected")

    def _detect_unity_screen(self, ss, gx, gy, gw, gh):
        """Annotate Unity Cup screens: opponents, launch/select buttons."""
        begin_pos = self.vision.find_template("btn_begin_showdown", ss, 0.70)
        is_popup = begin_pos is not None

        if is_popup:
            self.info_lines.append("Unity: confirmation popup")
            self.detections.append(dict(
                type="point", label="begin_showdown",
                color=(0, 255, 128), x=begin_pos[0], y=begin_pos[1],
                cat="unity"))
            cancel = self.vision.find_template("btn_cancel", ss, 0.70)
            if cancel:
                self.detections.append(dict(
                    type="point", label="cancel",
                    color=(0, 128, 255), x=cancel[0], y=cancel[1],
                    cat="unity"))
            return

        opponents = self.vision.detect_unity_opponents(ss)
        if opponents:
            self.info_lines.append(f"Opponents: {len(opponents)}")
            for i, (ox, oy) in enumerate(opponents):
                self.detections.append(dict(
                    type="point", label=f"opponent {i+1}",
                    color=(0, 200, 255), x=ox, y=oy, cat="unity"))

        unity_btns = ["btn_unity_launch", "btn_select_opponent",
                      "btn_begin_showdown", "btn_see_unity_results",
                      "btn_next_unity", "btn_launch_final_unity"]
        for btn in unity_btns:
            pos = self.vision.find_template(btn, ss, 0.70)
            if pos:
                short = btn.replace("btn_", "")
                self.detections.append(dict(
                    type="point", label=short, color=(0, 255, 128),
                    x=pos[0], y=pos[1], cat="unity"))
                self.info_lines.append(f"Unity btn: {short}")

    def _detect_skills_screen(self, ss, gx, gy, gw, gh):
        self.info_lines.append("Skills screen detected")

        buy_icons = self.vision.find_all_template("buy_skill", ss, 0.82, min_distance=20)
        visible = [(bx, by) for bx, by in buy_icons
                   if gy + int(gh * 0.20) < by < gy + int(gh * 0.95)]

        for bx, by in visible:
            active = self._skill_icon_active(ss, bx, by)
            dot_color = (0, 220, 60) if active else (0, 60, 220)

            name, name_raw = self._ocr_skill_name_at(ss, bx, by, gx, gw, gh, gy)
            cost = self._ocr_skill_cost_at(ss, bx, by, gw, gh)
            state = "BUY" if active else "locked"

            if name:
                label = f"{name} [{cost}SP] {state}"
            else:
                label = f"[{cost}SP] {state}"

            self.detections.append(dict(
                type="point", label=label,
                color=dot_color, x=bx, y=by, cat="skill"))
            self.info_lines.append(f"  {label}")
            self.info_lines.append(f"    raw_ocr: '{name_raw}'")

        if not visible:
            self.info_lines.append("  no buy_skill icons visible")

        tpl_close_path = Path("templates/skills/btn_close.png")
        close_popup_active = False
        if tpl_close_path.exists():
            tpl_close = cv2.imread(str(tpl_close_path))
            gx, gy, gw, gh = self.vision.get_game_rect(ss)
            game = ss[gy:gy+gh, gx:gx+gw]
            if tpl_close is not None and tpl_close.shape[0] <= game.shape[0] and tpl_close.shape[1] <= game.shape[1]:
                res = cv2.matchTemplate(game, tpl_close, cv2.TM_CCOEFF_NORMED)
                _, mv, _, ml = cv2.minMaxLoc(res)
                if mv >= 0.75:
                    cx = gx + ml[0] + tpl_close.shape[1] // 2
                    cy = gy + ml[1] + tpl_close.shape[0] // 2
                    self.detections.append(dict(
                        type="point", label=f"close ({mv:.2f})", color=(255, 200, 0),
                        x=cx, y=cy, cat="skill"))
                    self.info_lines.append(f"  close: ({cx},{cy}) conf={mv:.3f}")
                    close_popup_active = True
                else:
                    self.info_lines.append(f"  close: not found (best={mv:.3f})")

        if not close_popup_active:
            for btn, thr, label in [("learn_btn", 0.72, "learn"), ("confirm_btn", 0.72, "confirm")]:
                pos = self.vision.find_template(btn, ss, thr)
                if pos:
                    self.detections.append(dict(
                        type="point", label=label, color=(0, 255, 128),
                        x=pos[0], y=pos[1], cat="skill"))
                    self.info_lines.append(f"  {label}: {pos}")

        for btn, thr, label in [("btn_back", 0.72, "back")]:
            pos = self.vision.find_template(btn, ss, thr)
            if pos:
                self.detections.append(dict(
                    type="point", label=label, color=(255, 200, 0),
                    x=pos[0], y=pos[1], cat="skill"))
                self.info_lines.append(f"  {label}: {pos}")

    @staticmethod
    def _skill_icon_active(ss: np.ndarray, x: int, y: int, radius: int = 18) -> bool:
        y1 = max(0, y - radius)
        y2 = min(ss.shape[0], y + radius)
        x1 = max(0, x - radius)
        x2 = min(ss.shape[1], x + radius)
        roi = ss[y1:y2, x1:x2]
        if roi.size == 0:
            return False
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        green_mask = (
            (hsv[:, :, 0] >= 35) & (hsv[:, :, 0] <= 85) &
            (hsv[:, :, 1] >= 60) &
            (hsv[:, :, 2] >= 100)
        )
        green_ratio = float(np.sum(green_mask)) / max(1, roi.shape[0] * roi.shape[1])
        return green_ratio >= 0.10

    @staticmethod
    def _ocr_skill_name_at(ss: np.ndarray, icon_x: int, icon_y: int,
                            gx: int, gw: int, gh: int, gy: int):
        from scripts.vision.ocr import _ocr_text_raw
        x1 = gx + int(gw * 0.08)
        x2 = gx + int(gw * 0.73)
        search_top = max(gy, icon_y - int(gh * 0.130))
        search_bot = max(gy + 1, icon_y - int(gh * 0.008))

        scan = ss[search_top:search_bot, x1:x2]
        if scan.size == 0:
            return "", ""

        gray_scan = cv2.cvtColor(scan, cv2.COLOR_BGR2GRAY).astype(float)

        edge_rows = []
        for rel_y in range(gray_scan.shape[0]):
            grad = float(np.abs(np.diff(gray_scan[rel_y])).mean())
            if grad > 2.0:
                edge_rows.append(rel_y)

        if not edge_rows:
            return "", ""

        clusters = []
        cluster = [edge_rows[0]]
        for r in edge_rows[1:]:
            if r - cluster[-1] <= 4:
                cluster.append(r)
            else:
                clusters.append(cluster)
                cluster = [r]
        clusters.append(cluster)

        scan_h = scan.shape[0]
        for min_dist_frac in [0.10, 0.05, 0.02]:
            min_dist = max(3, int(scan_h * min_dist_frac))
            candidates = [c for c in clusters if scan_h - max(c) > min_dist]
            if candidates:
                break
        if not candidates:
            return "", ""

        title_cluster = candidates[-1]
        t_y1 = max(0, min(title_cluster) - 3)
        t_y2 = min(scan.shape[0], max(title_cluster) + 6)
        roi = scan[t_y1:t_y2]
        if roi.size == 0:
            return "", ""

        try:
            Path("logs/debug").mkdir(parents=True, exist_ok=True)
            cv2.imwrite(f"logs/debug/skill_name_roi_{icon_y % 1000}.png", roi)
        except Exception:
            pass

        scale = 3
        big = cv2.resize(roi, (roi.shape[1] * scale, roi.shape[0] * scale),
                         interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY)

        best_raw = ""
        for t in [100, 120, 80]:
            _, th = cv2.threshold(gray, t, 255, cv2.THRESH_BINARY_INV)
            dark_pct = float((th > 0).sum()) / max(1, th.size) * 100
            if 2.0 <= dark_pct <= 20.0:
                try:
                    candidate = _ocr_text_raw(th).strip()
                    if len(candidate) > len(best_raw):
                        best_raw = candidate
                except Exception:
                    pass
        if not best_raw:
            _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            try:
                best_raw = _ocr_text_raw(th).strip()
            except Exception:
                pass

        snapped = VisualDebugTool._snap_skill_name(best_raw)
        return snapped, best_raw

    @staticmethod
    def _snap_skill_name(raw: str) -> str:
        if not raw:
            return ""
        try:
            from difflib import SequenceMatcher as _SM
            import json as _json
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(root, "config", "skills.json")
            if not os.path.exists(db_path):
                db_path = os.path.join("config", "skills.json")
            if not os.path.exists(db_path):
                return raw
            with open(db_path, encoding="utf-8") as f:
                skills = _json.load(f)
            names = [s["name"] for s in skills]
            raw_words = set(raw.lower().split())
            best_name = raw
            best_score = 0.0
            for n in names:
                n_words = set(n.lower().replace("◎", "").replace("○", "").split())
                if raw_words & n_words:
                    word_score = len(raw_words & n_words) / max(1, len(n_words))
                    seq_score = _SM(None, raw.lower(), n.lower()).ratio()
                    score = word_score * 0.6 + seq_score * 0.4
                else:
                    score = _SM(None, raw.lower(), n.lower()).ratio()
                if score > best_score:
                    best_score = score
                    best_name = n
            return best_name if best_score >= 0.25 else raw
        except Exception:
            return raw

    @staticmethod
    def _ocr_skill_cost_at(ss: np.ndarray, icon_x: int, icon_y: int,
                            gw: int, gh: int) -> str:
        from scripts.vision.ocr import _ocr_digits
        cost_x1 = max(0, icon_x - int(gw * 0.12))
        cost_x2 = max(0, icon_x - int(gw * 0.01))
        cost_y1 = max(0, icon_y - int(gh * 0.022))
        cost_y2 = min(ss.shape[0], icon_y + int(gh * 0.022))
        if cost_x2 <= cost_x1 or cost_y2 <= cost_y1:
            return "?"
        roi = ss[cost_y1:cost_y2, cost_x1:cost_x2]
        if roi.size == 0:
            return "?"
        scale = 3
        big = cv2.resize(roi, (roi.shape[1] * scale, roi.shape[0] * scale),
                         interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)
        try:
            result = _ocr_digits(thresh).strip()
            return result if result else "?"
        except Exception:
            return "?"

    def _detect_events(self, ss, gx, gy, gw, gh):
        event_type = None
        for ew in EVENT_WINDOWS:
            pos = self.vision.find_template(ew, ss, 0.80)
            if pos:
                short = ew.replace("event_", "").replace("_window", "")
                event_type = short
                self.detections.append(dict(
                    type="point", label=f"ev_{short}",
                    color=COLORS["event_window"],
                    x=pos[0], y=pos[1], cat="event_win"))
                self.info_lines.append(f"Event window: {short}")
                break

        ec = self.vision._calibration.get("event_choices", {})
        choices = self.vision.find_all_template("event_choice", ss, 0.75, min_distance=30)
        y_min = gy + int(gh * ec.get("y1", 0.35))
        y_max = gy + int(gh * ec.get("y2", 0.85))
        valid = [c for c in choices if gx <= c[0] <= gx + gw and y_min <= c[1] <= y_max]
        valid.sort(key=lambda p: p[1])

        if valid and not event_type:
            non_event_buttons = [
                "btn_ok", "btn_claw_machine", "btn_race_launch",
                "btn_race_start", "btn_race_start_ura", "btn_race_next_finish",
                "btn_begin_showdown", "btn_see_unity_results", "btn_next_unity",
                "btn_launch_final_unity", "btn_unity_launch", "btn_select_opponent",
                "btn_try_again", "btn_cancel",
            ]
            is_non_event = any(
                self.vision.find_template(b, ss, 0.70) for b in non_event_buttons
            )
            if is_non_event:
                self.info_lines.append(f"Event choices suppressed (non-event button visible)")
                valid = []

        for cx, cy in valid:
            self.detections.append(dict(
                type="point", label="choice", color=COLORS["event_choice"],
                x=cx, y=cy, cat="event_choice"))
        if valid:
            self.info_lines.append(f"Event choices: {len(valid)}")

        if not event_type and not valid:
            return

        title = self.vision.read_event_title(ss)
        if title:
            self.info_lines.append(f"Event title: {title}")

        choice_texts = []
        if valid:
            choice_texts = self.vision.read_choice_texts(ss, valid)
            for i, ct in enumerate(choice_texts):
                self.info_lines.append(f"  Choice {i+1}: {ct}")

        self._lookup_event_database(title, choice_texts, valid)

    def _lookup_event_database(self, title: str, choice_texts: list, choice_positions: list):
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "event_database.json")
        if not os.path.exists(db_path):
            self.info_lines.append("  [DB] event_database.json not found")
            return
        with open(db_path, encoding="utf-8") as f:
            db = json.load(f)

        search_text = (title or "").strip()
        if not search_text:
            self.info_lines.append("  [DB] No title to search")
            return

        all_events = []
        for char_name, char_events in db.get("character_events", {}).items():
            for event_name, data in char_events.items():
                all_events.append((event_name, data, f"character ({char_name})"))

        for card_name, card_data in db.get("support_card_events", {}).items():
            for event_name, data in card_data.get("events", {}).items():
                all_events.append((event_name, data, f"support ({card_name})"))

        for event_name, data in db.get("common_events", {}).items():
            all_events.append((event_name, data, "common"))

        best_name = None
        best_data = None
        best_source = None
        best_score = 0.0

        for event_name, data, source in all_events:
            score = self._match_score(event_name, search_text)
            if score > best_score:
                best_score = score
                best_name = event_name
                best_data = data
                best_source = source

        if best_name and best_score >= 0.5:
            pct = f"{best_score:.0%}"
            self.info_lines.append(f"  [DB] Match: \"{best_name}\" ({best_source}) [{pct}]")

            choices_data = best_data.get("choices", {})
            for num in sorted(choices_data.keys(), key=lambda x: int(x) if x.isdigit() else 0):
                c = choices_data[num]
                desc = c.get("description", "")
                label = f"Choice {num}" if num != "0" else "Auto"
                desc_part = f" ({desc})" if desc and desc != "auto" else ""

                if "outcomes" in c:
                    self.info_lines.append(f"    {label}{desc_part}:")
                    for variant, outcome in c["outcomes"].items():
                        self.info_lines.append(f"      [{variant}] {self._format_outcome(outcome)}")
                else:
                    self.info_lines.append(f"    {label}{desc_part}: {self._format_outcome(c)}")

            if best_data.get("note"):
                self.info_lines.append(f"  [DB] Note: {best_data['note']}")
        else:
            self.info_lines.append(f"  [DB] No match found for \"{title}\"")

    @staticmethod
    def _format_outcome(data):
        parts = []
        eff = data.get("effects", {})
        if eff:
            parts.append(", ".join(f"{k}: {v:+d}" for k, v in eff.items()))
        skills = data.get("skills", [])
        if skills:
            sk_strs = []
            for s in skills:
                if isinstance(s, dict):
                    sk_strs.append(f"{s['name']} +{s['level']}")
                else:
                    sk_strs.append(str(s))
            parts.append("skills: " + ", ".join(sk_strs))
        conds = data.get("conditions", [])
        if conds:
            parts.append("cond: " + ", ".join(conds))
        return " | ".join(parts) or "(no effects)"

    @staticmethod
    def _match_score(event_name: str, ocr_title: str) -> float:
        a = event_name.lower().strip()
        b = ocr_title.lower().strip()
        if not a or not b:
            return 0.0
        if a == b:
            return 1.0
        if a in b:
            return 0.95
        return SequenceMatcher(None, a, b).ratio()

    def _detect_calibrated_rois(self, ss, gx, gy, gw, gh):
        roi_names = [
            "energy_bar", "support_region", "date_display",
            "event_title", "event_choices", "training_zone", "mood_zone",
        ]
        for name in roi_names:
            r = self.vision._calibration.get(name)
            if r and "x1" in r:
                x1 = gx + int(gw * r["x1"])
                y1 = gy + int(gh * r["y1"])
                x2 = gx + int(gw * r["x2"])
                y2 = gy + int(gh * r["y2"])
                self.detections.append(dict(
                    type="rect", label=name, color=COLORS["roi"],
                    x1=x1, y1=y1, x2=x2, y2=y2, cat="roi", dashed=True))

    def render(self):
        self.overlay = self.screenshot.copy()
        h, w = self.overlay.shape[:2]

        for det in self.detections:
            cat = det.get("cat", "")
            if self.mode == "detections" and cat == "roi":
                continue
            if self.mode == "regions" and cat not in ("roi", "frame", "column"):
                continue

            col = det["color"]
            label = det.get("label", "")

            if det["type"] == "rect":
                x1, y1, x2, y2 = det["x1"], det["y1"], det["x2"], det["y2"]
                if det.get("dashed"):
                    self._draw_dashed_rect(self.overlay, (x1, y1), (x2, y2), col, 1)
                else:
                    cv2.rectangle(self.overlay, (x1, y1), (x2, y2), col, 2)
                if label:
                    _put_label(self.overlay, label, x1 + 4, y1 + 16, col, 0.55, 1)

            elif det["type"] == "point":
                x, y = det["x"], det["y"]
                cv2.circle(self.overlay, (x, y), 16, col, 2)
                cv2.circle(self.overlay, (x, y), 3, col, -1)
                if label:
                    _put_label(self.overlay, label, x + 20, y + 5, col, 0.55, 1)

            elif det["type"] == "vline":
                x = det["x"]
                y1, y2 = det["y1"], det["y2"]
                for yy in range(y1, y2, 10):
                    cv2.line(self.overlay, (x, yy), (x, min(yy + 5, y2)), col, 1)

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.50
        line_h = 20
        text_pad = 6

        gx_r, gy_r, gw_r, gh_r = self.vision.get_game_rect(self.screenshot)
        panel_right_max = max(0, gx_r - 4)
        if panel_right_max < 120:
            panel_right_max = min(w, gx_r + gw_r + 4 + 450)
            panel_x = gx_r + gw_r + 4
        else:
            panel_x = 0

        max_tw = 0
        for line in self.info_lines:
            (tw, _), _ = cv2.getTextSize(line, font, font_scale, 1)
            if tw > max_tw:
                max_tw = tw
        avail_w = (panel_right_max - panel_x) if panel_x == 0 else (w - panel_x)
        panel_w = min(max_tw + text_pad * 2 + 10, avail_w)
        panel_h = min(16 + len(self.info_lines) * line_h, h)

        px1 = panel_x
        px2 = panel_x + panel_w
        sub = self.overlay[0:panel_h, px1:px2]
        if sub.size > 0:
            self.overlay[0:panel_h, px1:px2] = (sub * 0.20).astype(np.uint8)

        y_text = 16
        for line in self.info_lines:
            cv2.putText(self.overlay, line, (px1 + text_pad, y_text),
                        font, font_scale, (255, 255, 255), 1, cv2.LINE_AA)
            y_text += line_h

        bar_h = 50
        sub_b = self.overlay[h - bar_h:h, 0:w]
        if sub_b.size > 0:
            self.overlay[h - bar_h:h, 0:w] = (sub_b * 0.3).astype(np.uint8)
        mode_t = f"Mode: {self.mode} | Thresh: {self.threshold_offset:+.2f} | ROIs: {'ON' if self.show_rois else 'OFF'}"
        cv2.putText(self.overlay, mode_t, (10, h - 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1, cv2.LINE_AA)
        cv2.putText(self.overlay, "Space=refresh  S=save  T=mode  R=ROIs  D=diagnose  C=capture  Q=quit",
                    (10, h - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (160, 160, 160), 1, cv2.LINE_AA)

    @staticmethod
    def _draw_dashed_rect(img, pt1, pt2, color, thickness):
        x1, y1 = pt1
        x2, y2 = pt2
        d, g = 10, 7
        for x in range(x1, x2, d + g):
            cv2.line(img, (x, y1), (min(x + d, x2), y1), color, thickness)
            cv2.line(img, (x, y2), (min(x + d, x2), y2), color, thickness)
        for y in range(y1, y2, d + g):
            cv2.line(img, (x1, y), (x1, min(y + d, y2)), color, thickness)
            cv2.line(img, (x2, y), (x2, min(y + d, y2)), color, thickness)

    def save_annotated(self):
        Path("logs/debug").mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = f"logs/debug/visual_debug_{ts}.png"
        cv2.imwrite(path, self.overlay)
        print(f"Saved: {path}")

    def diagnose(self):
        """Diagnostic complet : main buttons, infirmary ON/OFF, training zone."""
        ss = self.screenshot
        gx, gy, gw, gh = self.vision.get_game_rect(ss)
        game = ss[gy:gy+gh, gx:gx+gw]

        # ── 1. MAIN SCREEN BUTTONS ──────────────────────────────────────────
        print(f"\n{'='*60}")
        print(f"DIAGNOSE — Main Screen Buttons")
        print(f"{'='*60}")

        main_buttons = [
            ("btn_training",      0.70),
            ("btn_rest",          0.70),
            ("btn_recreation",    0.70),
            ("btn_races",         0.70),
            ("btn_rest_summer",   0.70),
            ("btn_skills",        0.72),
            ("btn_infirmary",     0.60),
        ]

        for tpl_name, thresh in main_buttons:
            tpl = self.vision._get_scaled_template(tpl_name)
            if tpl is None:
                print(f"  {tpl_name:22s}  FILE MISSING")
                continue
            th, tw = tpl.shape[:2]
            if th > game.shape[0] or tw > game.shape[1]:
                print(f"  {tpl_name:22s}  {tw}x{th} — TOO LARGE")
                continue
            found = self.vision.find_template(tpl_name, ss, thresh)
            detected = "DETECTED" if found else "NOT FOUND"
            res = cv2.matchTemplate(game, tpl, cv2.TM_CCOEFF_NORMED)
            _, mv, _, _ = cv2.minMaxLoc(res)
            status = "MATCH" if mv >= thresh else "no match"
            print(f"  {tpl_name:22s}  {tw:3d}x{th:3d}  conf={mv:.4f}  {status}  {detected}")

        # ── 2. INFIRMARY ON vs OFF ───────────────────────────────────────────
        print(f"\n{'='*60}")
        print(f"DIAGNOSE — Infirmary ON vs OFF")
        print(f"{'='*60}")

        t_on = self.vision._get_scaled_template("btn_infirmary")

        if t_on is None:
            print("  MISSING template btn_infirmary")
        else:
            search, ox, oy = self.vision._get_search_area("btn_infirmary", ss)
            if search.shape[0] >= t_on.shape[0] and search.shape[1] >= t_on.shape[1]:
                res = cv2.matchTemplate(search, t_on, cv2.TM_CCOEFF_NORMED)
                _, mv_on, _, ml_on = cv2.minMaxLoc(res)

                th_on, tw_on = t_on.shape[:2]
                x1, y1 = ml_on
                roi = search[y1:y1 + th_on, x1:x1 + tw_on]

                ref_brightness = float(np.mean(cv2.cvtColor(t_on, cv2.COLOR_BGR2GRAY))) if t_on.size > 0 else 0.0
                roi_brightness = float(np.mean(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY))) if roi.size > 0 else 0.0
                brightness_diff = abs(roi_brightness - ref_brightness) / ref_brightness if ref_brightness > 0 else 1.0
                brightness_match = brightness_diff <= 0.15

                detect_result = self.vision.detect_injury(ss)

                print(f"  Template btn_infirmary : {tw_on}x{th_on}  ref_brightness={ref_brightness:.1f}")
                print(f"  Score ON     : {mv_on:.4f}  {'✓ MATCH (>=0.60)' if mv_on >= 0.60 else '✗ no match (<0.60, stop ici)'}")
                print(f"")
                print(f"  ROI brightness      : {roi_brightness:.1f}")
                print(f"  Ref brightness      : {ref_brightness:.1f}")
                print(f"  Diff relative       : {brightness_diff:.3f}  (seuil = 0.15)")
                print(f"  Brightness match    : {'✓ OUI -> bouton allume (ON)' if brightness_match else 'X NON -> bouton eteint (OFF)'}")
                print(f"")
                print(f"  +--RESULTAT FINAL-------------------------------------------+")
                print(f"  | detect_injury() = {'True  => INJURY detecte (bouton ON)' if detect_result else 'False => PAS de blessure (bouton OFF)'}")
                print(f"  +-----------------------------------------------------------+")

                Path("logs/debug").mkdir(parents=True, exist_ok=True)
                if roi.size > 0:
                    cv2.imwrite("logs/debug/infirmary_detected_roi.png", roi)
                    print(f"  ROI sauvegardee : logs/debug/infirmary_detected_roi.png")


        # ── 3. TRAINING ZONE ────────────────────────────────────────────────
        print(f"\n{'='*60}")
        tz = self.vision._calibration.get("training_zone", {})
        tx1 = max(0, gx + int(gw * tz.get("x1", 0)))
        ty1 = max(0, gy + int(gh * tz.get("y1", 0)))
        tx2 = min(ss.shape[1], gx + int(gw * tz.get("x2", 1)))
        ty2 = min(ss.shape[0], gy + int(gh * tz.get("y2", 1)))
        search = ss[ty1:ty2, tx1:tx2]
        print(f"DIAGNOSE — Training zone: ({tx1},{ty1})→({tx2},{ty2}) = {search.shape[1]}x{search.shape[0]}")
        print(f"{'='*60}")

        aliases = self.vision._TPL_FILE_ALIASES
        all_tpls = [
            ("burst_white", 0.80), ("burst_blue", 0.80),
            ("icon_rainbow", 0.75),
            ("friend_bar_partial", 0.70), ("friend_bar_orange", 0.70),
            ("friend_bar_max", 0.70), ("friend_bar_burst", 0.70),
        ]
        for tpl_name, thresh in all_tpls:
            fname = aliases.get(tpl_name, tpl_name)
            tpl = self.vision._get_scaled_template(fname)
            if tpl is None:
                print(f"  {tpl_name:25s}  FILE MISSING ({fname}.png)")
                continue
            th, tw = tpl.shape[:2]
            if th > search.shape[0] or tw > search.shape[1]:
                print(f"  {tpl_name:25s}  {tw}x{th} — TOO LARGE for zone")
                continue
            res = cv2.matchTemplate(search, tpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            status = "✓ MATCH" if max_val >= thresh else "✗ no match"
            print(f"  {tpl_name:25s}  {tw:3d}x{th:3d}  conf={max_val:.4f}  thresh={thresh}  {status}")

            if th <= game.shape[0] and tw <= game.shape[1]:
                res_full = cv2.matchTemplate(game, tpl, cv2.TM_CCOEFF_NORMED)
                _, mv_full, _, ml_full = cv2.minMaxLoc(res_full)
                if mv_full > max_val + 0.05:
                    rel_y = (ml_full[1] + th//2) / gh
                    print(f"    {'':25s}  → in full game: conf={mv_full:.4f} at rel_y={rel_y:.3f} (OUTSIDE training zone!)")

        bar_info = self.vision._count_support_bars(ss)
        print(f"\nSupport bars (thin gauge): {bar_info['total']}")
        for ys, ye, bt in bar_info['bars']:
            print(f"  y={ys}-{ye} ({ye-ys+1}px) type={bt}")
        print(f"{'='*60}\n")

        # ── 4. BTN_CLOSE (Skills popup) ─────────────────────────────────────
        print(f"\n{'='*60}")
        print(f"DIAGNOSE — btn_close (templates/skills/btn_close.png)")
        print(f"{'='*60}")

        tpl_path = Path("templates/skills/btn_close.png")
        if not tpl_path.exists():
            print(f"  FILE NOT FOUND: {tpl_path}")
        else:
            tpl = cv2.imread(str(tpl_path))
            th, tw = tpl.shape[:2]
            print(f"  Template size : {tw}x{th} px")
            print(f"  Game rect     : ({gx},{gy}) {gw}x{gh}")

            tpl_gray = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
            game_gray = cv2.cvtColor(game, cv2.COLOR_BGR2GRAY)

            if th <= game.shape[0] and tw <= game.shape[1]:
                res_color = cv2.matchTemplate(game, tpl, cv2.TM_CCOEFF_NORMED)
                res_gray  = cv2.matchTemplate(game_gray, tpl_gray, cv2.TM_CCOEFF_NORMED)

                _, mv_c, _, ml_c = cv2.minMaxLoc(res_color)
                _, mv_g, _, ml_g = cv2.minMaxLoc(res_gray)

                cx_c = gx + ml_c[0] + tw // 2
                cy_c = gy + ml_c[1] + th // 2
                cx_g = gx + ml_g[0] + tw // 2
                cy_g = gy + ml_g[1] + th // 2

                print(f"\n  [COLOR]  best_conf={mv_c:.4f}  at screen ({cx_c},{cy_c})  rel_y={ml_c[1]/gh:.3f}")
                print(f"  [GRAY ]  best_conf={mv_g:.4f}  at screen ({cx_g},{cy_g})  rel_y={ml_g[1]/gh:.3f}")

                print(f"\n  Top 5 matches (COLOR):")
                flat = res_color.flatten()
                flat.sort()
                flat = flat[::-1]
                for i, score in enumerate(flat[:5]):
                    locs = np.where(res_color >= score)
                    if len(locs[0]) > 0:
                        y0, x0 = locs[0][0], locs[1][0]
                        print(f"    #{i+1}  conf={score:.4f}  screen=({gx+x0+tw//2},{gy+y0+th//2})  rel_y={y0/gh:.3f}")

                print(f"\n  Threshold sweep (COLOR):")
                for thr in [0.90, 0.85, 0.80, 0.75, 0.70, 0.65, 0.60, 0.55, 0.50]:
                    hit = mv_c >= thr
                    print(f"    thr={thr:.2f}  {'✓ FOUND' if hit else '✗ not found'}  (best={mv_c:.4f})")

                Path("logs/debug").mkdir(parents=True, exist_ok=True)
                cv2.imwrite("logs/debug/btn_close_tpl.png", tpl)
                roi = game[ml_c[1]:ml_c[1]+th, ml_c[0]:ml_c[0]+tw]
                cv2.imwrite("logs/debug/btn_close_match_roi.png", roi)
                print(f"\n  Saved template   : logs/debug/btn_close_tpl.png")
                print(f"  Saved match ROI  : logs/debug/btn_close_match_roi.png")
            else:
                print(f"  Template {tw}x{th} is LARGER than game area {gw}x{gh} — cannot match")
        print(f"{'='*60}\n")


        # ── 5. PAL RECREATION POPUP ─────────────────────────────────────
        print(f"\n{'='*60}")
        print(f"DIAGNOSE — PAL Recreation popup")
        print(f"{'='*60}")

        rec_templates = [
            ("recreation_popup", 0.70, "Header vert (detecte la popup)"),
            ("arrow_empty",      0.65, "Fleche vide grise (PAL disponible)"),
            ("arrow_filled",     0.65, "Fleche pleine bleue (progression PAL)"),
            ("trainee_uma",      0.70, "Label Trainee Umamusume (dernier recours)"),
        ]

        for name, thresh, desc in rec_templates:
            pos = self.vision.find_template(name, ss, thresh)
            status = "MATCH" if pos else "no match"
            found_str = f"  at {pos}" if pos else ""
            print(f"  {name:25s}  conf>={thresh}  {status}{found_str}")
            print(f"    {desc}")

        print(f"\n  Simulation logique:")
        popup_pos = self.vision.find_template("recreation_popup", ss, 0.70)
        if not popup_pos:
            print(f"  -> popup non detectee")
        else:
            print(f"  -> popup detectee a {popup_pos}")
            empty_pts = self.vision.find_all_template("arrow_empty", ss, 0.65, min_distance=15)
            if empty_pts:
                sorted_e = sorted(empty_pts, key=lambda p2: p2[1])
                rows, cur = [], [sorted_e[0]]
                for pt in sorted_e[1:]:
                    if abs(pt[1] - cur[-1][1]) <= 50:
                        cur.append(pt)
                    else:
                        rows.append(cur)
                        cur = [pt]
                rows.append(cur)
                top_y = int(sum(p2[1] for p2 in rows[0]) / len(rows[0]))
                print(f"  -> {len(empty_pts)} fleche(s) vide(s) — {len(rows)} rangee(s) disponible(s)")
                print(f"  -> cliquerait rangee n1 a ({popup_pos[0]}, {top_y})")
                for i, row in enumerate(rows):
                    avg_y = int(sum(p2[1] for p2 in row) / len(row))
                    print(f"     rangee {i+1}: {len(row)} vide(s) y={avg_y}{' <- cible' if i == 0 else ''}")
            else:
                trainee_pos = self.vision.find_template("trainee_uma", ss, 0.70)
                if trainee_pos:
                    print(f"  -> 0 fleche vide (PAL completes) — cliquerait trainee a {trainee_pos}")
                else:
                    print(f"  -> 0 fleche vide ET trainee non detecte — Cancel")

        cv2.imwrite("logs/debug/pal_recreation_game.png", ss[gy:gy+gh, gx:gx+gw])
        print(f"\n  Zone jeu sauvegardee : logs/debug/pal_recreation_game.png")
        print(f"{'='*60}\n")

    def capture_template(self):
        """Let user draw a rectangle on the screenshot and save it as a template."""
        print("\nDraw a rectangle on the image, then press ENTER/SPACE to confirm.")
        print("Press C or ESC to cancel.")

        h, w = self.screenshot.shape[:2]
        scale = 1.0
        if h > 900:
            scale = 900 / h
        display = cv2.resize(self.screenshot, (int(w * scale), int(h * scale))) if scale < 1.0 else self.screenshot.copy()

        roi = cv2.selectROI("Capture Template", display, fromCenter=False, showCrosshair=True)
        cv2.destroyWindow("Capture Template")

        if roi[2] == 0 or roi[3] == 0:
            print("Cancelled.")
            return

        x = int(roi[0] / scale)
        y = int(roi[1] / scale)
        rw = int(roi[2] / scale)
        rh = int(roi[3] / scale)
        crop = self.screenshot[y:y+rh, x:x+rw]

        print(f"Captured region: {rw}x{rh} px")
        cv2.imshow("Preview", crop)
        print("Enter template name (e.g. friend_bar_partial): ", end="", flush=True)
        name = input().strip()
        cv2.destroyWindow("Preview")

        if not name:
            print("No name given — cancelled.")
            return

        path = f"templates/{name}.png"
        cv2.imwrite(path, crop)
        print(f"Saved: {path} ({rw}x{rh})")
        if name in self.vision.templates:
            del self.vision.templates[name]
        print("Template will be used on next refresh (Space).")

    def run(self):
        self.take_or_load_screenshot()
        self.detect_all()
        self.render()

        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
        disp_h = self.overlay.shape[0]
        if disp_h > 1000:
            s = 950 / disp_h
            cv2.resizeWindow(WINDOW_NAME,
                             int(self.overlay.shape[1] * s),
                             int(self.overlay.shape[0] * s))

        while True:
            cv2.imshow(WINDOW_NAME, self.overlay)
            key = cv2.waitKey(50) & 0xFF

            if key in (ord('q'), ord('Q'), 27):
                break
            elif key == ord(' '):
                print("Refreshing…")
                self.take_or_load_screenshot()
                self.detect_all()
                self.render()
            elif key in (ord('s'), ord('S')):
                self.save_annotated()
            elif key in (ord('t'), ord('T')):
                modes = ["all", "detections", "regions"]
                self.mode = modes[(modes.index(self.mode) + 1) % len(modes)]
                print(f"Mode: {self.mode}")
                self.render()
            elif key in (ord('r'), ord('R')):
                self.show_rois = not self.show_rois
                print(f"ROIs: {'ON' if self.show_rois else 'OFF'}")
                self.detect_all()
                self.render()
            elif key in (ord('+'), ord('=')):
                self.threshold_offset += 0.05
                print(f"Threshold offset: {self.threshold_offset:+.2f}")
                self.detect_all()
                self.render()
            elif key == ord('-'):
                self.threshold_offset -= 0.05
                print(f"Threshold offset: {self.threshold_offset:+.2f}")
                self.detect_all()
                self.render()
            elif key in (ord('d'), ord('D')):
                self.diagnose()
            elif key in (ord('c'), ord('C')):
                self.capture_template()

        cv2.destroyAllWindows()

        print("\n=== Detection Summary ===")
        for line in self.info_lines:
            try:
                print(f"  {line}")
            except UnicodeEncodeError:
                print(f"  {line.encode('ascii', 'replace').decode()}")

def main():
    parser = argparse.ArgumentParser(description="Visual Debug Tool")
    parser.add_argument("--screenshot", type=str, default=None,
                        help="Path to saved screenshot (skip live capture)")
    parser.add_argument("--config", type=str, default=os.path.join("config", "config.json"))
    parser.add_argument("--save", action="store_true",
                        help="Auto-save annotated + exit (no GUI)")
    args = parser.parse_args()

    tool = VisualDebugTool(config_path=args.config, screenshot_path=args.screenshot)
    if args.save:
        tool.take_or_load_screenshot()
        tool.detect_all()
        tool.render()
        tool.save_annotated()
        for line in tool.info_lines:
            print(f"  {line}")
    else:
        tool.run()

if __name__ == "__main__":
    main()