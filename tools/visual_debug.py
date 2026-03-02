import cv2
import numpy as np
import json
import sys
import os
import io
import time
import argparse
import threading
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from pathlib import Path
from difflib import SequenceMatcher

from PIL import Image, ImageTk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.vision import VisionModule
from scripts.vision.capture import CaptureMixin
from scripts.models import GameScreen

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
    "training_icon":  (255, 100, 0),
    "column":         (100, 100, 100),
    "energy_bar":     (0, 200, 255),
    "game_rect":      (0, 255, 0),
    "roi":            (255, 100, 100),
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
    "btn_try_again",
]

EVENT_WINDOWS = [
    "event_scenario_window", "event_trainee_window", "event_support_window",
]


def _put_label(img, text, x, y, color, scale=0.55, thickness=1):
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
                raise FileNotFoundError(f"Cannot load {self.screenshot_path}")
            self.screenshot = img
        else:
            self.vision.find_game_window()
            if not self.vision.game_hwnd:
                raise RuntimeError("Game window not found")
            self.screenshot = self.vision.take_screenshot()
        Path("logs/debug").mkdir(parents=True, exist_ok=True)
        cv2.imwrite("logs/debug/visual_debug_raw.png", self.screenshot)

    def capture_from_hwnd(self, hwnd):
        self.vision.game_hwnd = hwnd
        self.screenshot = self.vision.take_screenshot()
        Path("logs/debug").mkdir(parents=True, exist_ok=True)
        cv2.imwrite("logs/debug/visual_debug_raw.png", self.screenshot)

    def detect_all(self):
        self.detections = []
        self.info_lines = []
        ss = self.screenshot
        gx, gy, gw, gh = self.vision.get_game_rect(ss)

        self.screen = self.vision.detect_screen(ss)
        self.info_lines.append(f"Screen: {self.screen.value.upper()}")
        has_left = self.vision.get_template_path("anchor_left") is not None
        has_right = self.vision.get_template_path("anchor_right") is not None
        platform = self.vision.config.get("platform", "google_play")
        if platform == "steam" and self.vision._calibration.get("steam_game_rect"):
            src = f"steam calibration"
        elif has_left or has_right:
            parts = []
            if has_left:
                parts.append("L")
            if has_right:
                parts.append("R")
            src = f"anchors ({'+'.join(parts)})"
        elif self.vision._calibration.get("game_rect"):
            src = "calibration"
        else:
            src = "auto-detect"
        self.info_lines.append(f"Game area: ({gx},{gy}) {gw}x{gh} [{src}] platform={platform}")

        if platform == "steam":
            base_path = Path("config", "calibration.json")
            base_cal = {}
            if base_path.exists():
                try:
                    with open(base_path, encoding="utf-8") as f:
                        base_cal = json.load(f)
                except Exception:
                    pass
            steam_path = Path("config", "calibration_steam.json")
            steam_overrides = {}
            if steam_path.exists():
                try:
                    with open(steam_path, encoding="utf-8") as f:
                        steam_overrides = json.load(f)
                except Exception:
                    pass
            gp_rect = base_cal.get("game_rect", {})
            st_rect = base_cal.get("steam_game_rect", {})
            if gp_rect and st_rect and "x1" in gp_rect and "x1" in st_rect:
                gp_w = gp_rect["x2"] - gp_rect["x1"]
                st_w = st_rect["x2"] - st_rect["x1"]
                xr = gp_w / st_w if st_w > 0 else 1.0
                xo = (1.0 - xr) / 2.0
                n_manual = len(steam_overrides)
                skip = {"game_rect", "steam_game_rect"}
                n_auto = sum(1 for k, v in base_cal.items()
                             if k not in skip and k not in steam_overrides
                             and isinstance(v, dict) and ("x1" in v or "x" in v))
                self.info_lines.append(
                    f"Steam transform: x' = x*{xr:.4f}+{xo:.4f}  "
                    f"({n_manual} manual, {n_auto} auto)"
                )

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
                         GameScreen.RACE_SELECT, GameScreen.INSUFFICIENT_FANS,
                         GameScreen.SCHEDULED_RACE_POPUP):
            self._detect_energy(ss, gx, gy, gw, gh)
            self._detect_mood(ss)
            if self.screen in (GameScreen.MAIN, GameScreen.TRAINING):
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

        if self.screen in (GameScreen.INSUFFICIENT_FANS, GameScreen.SCHEDULED_RACE_POPUP):
            self._detect_insufficient_fans(ss, gx, gy, gw, gh)

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
            pos, conf = self.vision.find_template_conf("btn_inspiration", ss, 0.70)
            if pos:
                self.detections.append(dict(
                    type="point", label=f"inspiration ({conf:.2f})",
                    color=(0, 215, 255), x=pos[0], y=pos[1], cat="button"))
                self.info_lines.append(f"btn_inspiration: {pos} conf={conf:.3f}")

        if self.screen == GameScreen.CAREER_COMPLETE:
            for tpl in ["complete_career"]:
                pos, conf = self.vision.find_template_conf(tpl, ss, 0.75)
                if pos:
                    self.detections.append(dict(
                        type="point", label=f"{tpl} ({conf:.2f})", color=(0, 200, 255),
                        x=pos[0], y=pos[1], cat="career"))
                    self.info_lines.append(f"  {tpl}: {pos} conf={conf:.3f}")

        if self.screen != GameScreen.SKILL_SELECT:
            btns = GENERIC_BUTTONS
            if self.screen in (GameScreen.RACE_SELECT, GameScreen.RACE, GameScreen.TRY_AGAIN):
                btns = [b for b in GENERIC_BUTTONS if b != "btn_confirm"]
            self._detect_buttons(ss, gx, gw, btns, "gen_btn")

        if self.show_rois:
            self._detect_calibrated_rois(ss, gx, gy, gw, gh)

    def _detect_energy(self, ss, gx, gy, gw, gh):
        energy = self.vision.read_energy_percentage(ss)
        self.info_lines.append(f"Energy: {energy:.0f}%")
        xf = self.vision._aspect_x_factor(gw, gh)
        eb = self.vision._calibration.get("energy_bar", {})
        y1 = gy + int(gh * eb.get("y1", 0.082))
        y2 = gy + int(gh * eb.get("y2", 0.098))
        x1 = gx + int(gw * eb.get("x1", 0.33) * xf)
        x2 = gx + int(gw * eb.get("x2", 0.69) * xf)
        self.detections.append(dict(
            type="rect", label=f"Energy {energy:.0f}%",
            color=COLORS["energy_bar"],
            x1=x1, y1=y1, x2=x2, y2=y2, cat="energy"))

    def _detect_mood(self, ss):
        mood = self.vision.detect_mood(ss)
        self.info_lines.append(f"Mood: {mood}")
        if mood != "unknown":
            gx, gy, gw, gh = self.vision.get_game_rect(ss)
            mz = self.vision._calibration.get("mood_zone", {})
            cx = gx + int(gw * (mz.get("x1", 0.70) + mz.get("x2", 0.90)) / 2)
            cy = gy + int(gh * (mz.get("y1", 0.095) + mz.get("y2", 0.155)) / 2)
            self.detections.append(dict(
                type="point", label=f"mood: {mood}",
                color=COLORS["mood"], x=cx, y=cy, cat="mood"))

    def _detect_stats(self, ss):
        gx, gy, gw, gh = self.vision.get_game_rect(ss)
        ocr_y1 = gy + int(gh * 0.665)
        ocr_y2 = gy + int(gh * 0.690)
        for name in self.vision.STAT_NAMES:
            cal = self.vision._calibration.get(f"stat_{name}")
            if cal and "x1" in cal:
                rx1 = max(0, gx + int(gw * cal["x1"]))
                rx2 = min(ss.shape[1], gx + int(gw * cal["x2"]))
                self.detections.append(dict(
                    type="rect", label=f"stat_{name}", color=(0, 180, 255),
                    x1=rx1, y1=ocr_y1, x2=rx2, y2=ocr_y2, cat="roi", dashed=True))

        stats = self.vision.read_stats(ss)
        if stats:
            parts = [f"{n[:3].title()}={stats[n]}" for n in self.vision.STAT_NAMES
                     if n in stats]
            self.info_lines.append(f"Stats: {' | '.join(parts)}")
        else:
            self.info_lines.append("Stats: unreadable")

    def _detect_training_items(self, ss, gx, gy, gw, gh):
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
            xf = self.vision._aspect_x_factor(gw, gh)
            sx1 = gx + int(gw * sr["x1"] * xf)
            sy1 = gy + int(gh * sr["y1"])
            sx2 = gx + int(gw * sr["x2"] * xf)
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
                                xf2 = self.vision._aspect_x_factor(gw, gh)
                                icon_y = icon_positions[i][0]
                                iy = gy + int(gh * sr2["y1"]) + icon_y
                                ix = gx + int(gw * sr2["x1"] * xf2)
                                ix2 = gx + int(gw * sr2["x2"] * xf2)
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
            pos, conf = self.vision.find_template_conf(tpl, ss, 0.55)
            if pos:
                short = tpl.replace("training_", "")
                self.detections.append(dict(
                    type="point", label=f"{short} ({conf:.2f})",
                    color=COLORS["training_icon"],
                    x=pos[0], y=pos[1], cat="train_icon"))
                self.info_lines.append(f"  icon {short} at {pos} conf={conf:.3f}")

        self._detect_friendship_bars(ss)
        levels = self.vision.count_support_friendship_leveled(ss)
        self.info_lines.append(
            f"Friendship: partial={levels['partial']} orange+={levels['orange_plus']}"
            f" pal_orange={levels['pal_orange']} pal={'yes' if levels['pal'] else 'no'}"
        )

    def _detect_selected_training(self, ss, gx, gy, gw, gh):
        sel_pos, sel_conf = self.vision.find_template_conf("training_selected", ss, 0.60)
        if not sel_pos:
            return None

        xf = self.vision._aspect_x_factor(gw, gh)
        cal = self.vision._calibration
        best_stat = None
        best_dist = float("inf")
        for stat in ["speed", "stamina", "power", "guts", "wit"]:
            c = cal.get(f"train_{stat}")
            if c and "x" in c:
                cx = gx + int(gw * c["x"] * xf)
                dist = abs(sel_pos[0] - cx)
                if dist < best_dist:
                    best_dist = dist
                    best_stat = stat
        return best_stat

    def _detect_training_columns(self, ss, gx, gy, gw, gh):
        xf = self.vision._aspect_x_factor(gw, gh)
        cal = self.vision._calibration
        centers = {}
        for s in ["speed", "stamina", "power", "guts", "wit"]:
            c = cal.get(f"train_{s}")
            if c and "x" in c:
                centers[s] = gx + int(gw * c["x"] * xf)
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
        xf = self.vision._aspect_x_factor(gw, gh)
        sx1 = gx + int(gw * sr["x1"] * xf)
        sy1 = gy + int(gh * sr["y1"])
        sx2 = gx + int(gw * sr["x2"] * xf)
        for y_start, y_end, btype in bar_info["bars"]:
            band_color = COLORS.get(f"bar_{btype}", (200, 200, 200))
            self.detections.append(dict(
                type="rect", label=f"bar:{btype}", color=band_color,
                x1=sx1, y1=sy1 + y_start, x2=sx2, y2=sy1 + y_end,
                cat="friendship"))

    _DEBUG_BUTTONS = {"btn_rest", "btn_infirmary"}

    def _detect_infirmary(self, ss, gx, gw):
        self._raw_button_match(ss, gx, gw, "btn_infirmary", 0.55, "main_btn")

    def _detect_buttons(self, ss, gx, gw, btn_list, cat):
        for btn in btn_list:
            if btn in self._DEBUG_BUTTONS:
                self._raw_button_match(ss, gx, gw, btn, 0.70, cat)
            else:
                pos, conf = self.vision.find_template_conf(btn, ss, 0.70)
                if pos and gx <= pos[0] <= gx + gw:
                    short = btn.replace("btn_", "").replace("event_", "ev_")
                    self.detections.append(dict(
                        type="point", label=f"{short} ({conf:.2f})", color=COLORS["button"],
                        x=pos[0], y=pos[1], cat=cat))
                    if cat == "main_btn":
                        self.info_lines.append(f"  {short}: {pos} conf={conf:.3f}")

    def _raw_button_match(self, ss, gx, gw, name, threshold, cat):
        self.vision._update_scale(ss)
        tpl = self.vision._get_scaled_template(name)
        if tpl is None:
            self.info_lines.append(f"  {name}: NO TEMPLATE FILE")
            return
        search, ox, oy = self.vision._get_search_area(name, ss)
        short = name.replace("btn_", "")

        gx2, gy2, gw2, gh2 = self.vision.get_game_rect(ss)
        cal_name = self.vision._CAL_ALIASES.get(name, name)
        region = self.vision._calibration.get(cal_name)
        if region and "x1" in region:
            sa_x1 = max(0, gx2 + int(gw2 * region["x1"]))
            sa_y1 = max(0, gy2 + int(gh2 * region["y1"]))
            sa_x2 = min(ss.shape[1], gx2 + int(gw2 * region["x2"]))
            sa_y2 = min(ss.shape[0], gy2 + int(gh2 * region["y2"]))
            self.detections.append(dict(
                type="rect", label=f"search:{short}", color=(0, 255, 255),
                x1=sa_x1, y1=sa_y1, x2=sa_x2, y2=sa_y2, cat=cat, dashed=True))

        tpl_h, tpl_w = tpl.shape[:2]
        self.info_lines.append(
            f"  {short}: tpl={tpl_w}x{tpl_h} search={search.shape[1]}x{search.shape[0]} "
            f"scale={self.vision._current_scale:.3f}"
        )

        if search.shape[0] < tpl_h or search.shape[1] < tpl_w:
            need_h = max(0, tpl_h - search.shape[0])
            need_w = max(0, tpl_w - search.shape[1])
            new_y1 = max(0, oy - (need_h + 1) // 2)
            new_x1 = max(0, ox - (need_w + 1) // 2)
            new_y2 = min(ss.shape[0], oy + search.shape[0] + need_h // 2 + 1)
            new_x2 = min(ss.shape[1], ox + search.shape[1] + need_w // 2 + 1)
            search = ss[new_y1:new_y2, new_x1:new_x2]
            ox, oy = new_x1, new_y1
            self.info_lines.append(f"  {short}: expanded search to {search.shape[1]}x{search.shape[0]}")
            if search.shape[0] < tpl_h or search.shape[1] < tpl_w:
                self.info_lines.append(f"  {short}: SEARCH AREA TOO SMALL for template")
                return

        res = cv2.matchTemplate(search, tpl, cv2.TM_CCOEFF_NORMED)
        _, mv, _, ml = cv2.minMaxLoc(res)
        pos = (ox + ml[0] + tpl_w // 2, oy + ml[1] + tpl_h // 2)
        detected = mv >= threshold and gx <= pos[0] <= gx + gw

        if detected:
            color = COLORS["button"]
            label = f"{short} ({mv:.2f})"
        else:
            color = (0, 0, 255)
            label = f"{short} ({mv:.2f}) BELOW {threshold}"

        self.detections.append(dict(
            type="point", label=label, color=color,
            x=pos[0], y=pos[1], cat=cat))
        self.info_lines.append(f"  {short}: {pos} conf={mv:.3f} {'OK' if detected else 'FAIL'}")

        for extra_scale in [0.90, 0.95, 1.05, 1.10, 1.15]:
            nw = max(1, int(tpl_w * extra_scale))
            nh = max(1, int(tpl_h * extra_scale))
            if nh > search.shape[0] or nw > search.shape[1]:
                continue
            scaled = cv2.resize(tpl, (nw, nh), interpolation=cv2.INTER_AREA if extra_scale < 1 else cv2.INTER_LINEAR)
            r2 = cv2.matchTemplate(search, scaled, cv2.TM_CCOEFF_NORMED)
            _, mv2, _, ml2 = cv2.minMaxLoc(r2)
            self.info_lines.append(
                f"    scale {extra_scale:.2f}: conf={mv2:.3f} "
                f"pos=({ox + ml2[0] + nw // 2}, {oy + ml2[1] + nh // 2})"
            )

    def _detect_insufficient_fans(self, ss, gx, gy, gw, gh):
        insuf_pos, insuf_conf = self.vision.find_template_conf("insufficient_fans", ss, 0.65)
        sched_pos, sched_conf = self.vision.find_template_conf("scheduled_race_popup", ss, 0.65)

        self.info_lines.append(f"Banner comparison: insufficient={insuf_conf:.3f} scheduled_race={sched_conf:.3f}")

        if sched_pos:
            self.detections.append(dict(
                type="point", label=f"SCHED RACE POPUP ({sched_conf:.2f})",
                color=(0, 255, 255), x=sched_pos[0], y=sched_pos[1], cat="insuf_fans"))

        if not insuf_pos and not sched_pos:
            self.info_lines.append("No green banner template found")
            return

        if sched_conf >= 0.70 and sched_conf >= insuf_conf:
            self.info_lines.append("-> WINNER: scheduled_race_popup (must click Race)")
        elif insuf_conf >= 0.70:
            self.info_lines.append("-> WINNER: insufficient_fans")

        if insuf_pos:
            self.detections.append(dict(
                type="point", label=f"INSUFFICIENT FANS ({insuf_conf:.2f})",
                color=(0, 0, 255), x=insuf_pos[0], y=insuf_pos[1], cat="insuf_fans"))
            self.info_lines.append(f"Insufficient Fans popup: {insuf_pos} conf={insuf_conf:.3f}")

        cancel_pos, cancel_conf = self.vision.find_template_conf("btn_cancel", ss, 0.70)
        if cancel_pos:
            self.detections.append(dict(
                type="point", label=f"Cancel ({cancel_conf:.2f})",
                color=(128, 128, 255), x=cancel_pos[0], y=cancel_pos[1], cat="insuf_fans"))
            self.info_lines.append(f"  Cancel: {cancel_pos} conf={cancel_conf:.3f}")

            center_x = gx + gw // 2
            race_x = center_x + (center_x - cancel_pos[0])
            race_y = cancel_pos[1]
            self.detections.append(dict(
                type="point", label="Race (force)",
                color=(0, 255, 0), x=race_x, y=race_y, cat="insuf_fans"))
            self.info_lines.append(f"  Race (force): ({race_x}, {race_y})")
        else:
            xf = self.vision._aspect_x_factor(gw, gh)
            race_x = gx + int(gw * 0.65 * xf)
            race_y = insuf_pos[1] + int(gh * 0.30)
            self.detections.append(dict(
                type="point", label="Race (fallback)",
                color=(0, 255, 0), x=race_x, y=race_y, cat="insuf_fans"))
            self.info_lines.append(f"  Race (fallback): ({race_x}, {race_y})")

            cancel_x = gx + int(gw * 0.35 * xf)
            cancel_y = race_y
            self.detections.append(dict(
                type="point", label="Cancel (fallback)",
                color=(128, 128, 255), x=cancel_x, y=cancel_y, cat="insuf_fans"))
            self.info_lines.append(f"  Cancel (fallback): ({cancel_x}, {cancel_y})")

        force = self.config.get("race_strategy", {}).get(
            "force_race_insufficient_fans", True)
        self.info_lines.append(f"  force_race_insufficient_fans: {force}")

    def _detect_race_select(self, ss, gx, gy, gw, gh):
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
        RACE_PREP_BTNS = [
            ("race_view_results_on", 0.85), ("race_view_results_off", 0.70),
            ("btn_race_start", 0.70), ("btn_race_start_ura", 0.70),
            ("btn_race_launch", 0.70),
            ("btn_change_strategy", 0.70), ("btn_skip", 0.70),
        ]
        for btn, thr in RACE_PREP_BTNS:
            pos, conf = self.vision.find_template_conf(btn, ss, thr)
            if pos:
                short = btn.replace("race_view_results_", "vr_").replace("btn_", "")
                self.detections.append(dict(
                    type="point", label=f"{short} ({conf:.2f})", color=(0, 255, 0),
                    x=pos[0], y=pos[1], cat="race_prep"))
                self.info_lines.append(f"  {short}: {pos} conf={conf:.3f}")

    def _detect_pal_recreation_popup(self, ss, gx, gy, gw, gh):
        popup_pos, popup_conf = self.vision.find_template_conf("recreation_popup", ss, 0.70)
        if not popup_pos:
            return

        self.detections.append(dict(
            type="point", label=f"rec_popup ({popup_conf:.2f})",
            color=(60, 220, 60), x=popup_pos[0], y=popup_pos[1], cat="pal_rec"))
        self.info_lines.append(f"PAL Recreation popup detected conf={popup_conf:.3f}")

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

        trainee_pos, trainee_conf = self.vision.find_template_conf("trainee_uma", ss, 0.70)
        if trainee_pos:
            is_fallback = len(rows_with_empty) > 0
            label = f"trainee_uma ({trainee_conf:.2f}) (fallback)" if is_fallback else f"trainee_uma ({trainee_conf:.2f}) <- CLICK"
            color = (60, 60, 220) if is_fallback else (0, 220, 60)
            self.detections.append(dict(
                type="point", label=label, color=color,
                x=trainee_pos[0], y=trainee_pos[1], cat="pal_rec"))
            self.info_lines.append(
                f"  trainee_uma: {trainee_pos} conf={trainee_conf:.3f}"
                + (" (fallback only)" if is_fallback else " <- would click"))
        else:
            self.info_lines.append("  trainee_uma: template MISSING ou non detecte")

    def _detect_strategy_popup(self, ss, gx, gy, gw, gh):
        STRAT_BTNS = ["strategy_end", "strategy_late", "strategy_pace", "strategy_front"]
        found_any = False
        for btn in STRAT_BTNS:
            pos, conf = self.vision.find_template_conf(btn, ss, 0.80)
            if pos:
                short = btn.replace("strategy_", "")
                self.detections.append(dict(
                    type="point", label=f"{short} ({conf:.2f})", color=(255, 200, 0),
                    x=pos[0], y=pos[1], cat="strategy"))
                found_any = True
        if found_any:
            for btn in ["btn_confirm", "btn_cancel"]:
                pos, conf = self.vision.find_template_conf(btn, ss, 0.80)
                if pos:
                    short = btn.replace("btn_", "")
                    self.detections.append(dict(
                        type="point", label=f"{short} ({conf:.2f})", color=(0, 255, 0),
                        x=pos[0], y=pos[1], cat="strategy"))
            self.info_lines.append("Strategy popup detected")

    def _detect_unity_screen(self, ss, gx, gy, gw, gh):
        begin_pos, begin_conf = self.vision.find_template_conf("btn_begin_showdown", ss, 0.70)
        is_popup = begin_pos is not None

        if is_popup:
            self.info_lines.append("Unity: confirmation popup")
            self.detections.append(dict(
                type="point", label=f"begin_showdown ({begin_conf:.2f})",
                color=(0, 255, 128), x=begin_pos[0], y=begin_pos[1],
                cat="unity"))
            cancel, c_conf = self.vision.find_template_conf("btn_cancel", ss, 0.70)
            if cancel:
                self.detections.append(dict(
                    type="point", label=f"cancel ({c_conf:.2f})",
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
            pos, conf = self.vision.find_template_conf(btn, ss, 0.70)
            if pos:
                short = btn.replace("btn_", "")
                self.detections.append(dict(
                    type="point", label=f"{short} ({conf:.2f})", color=(0, 255, 128),
                    x=pos[0], y=pos[1], cat="unity"))
                self.info_lines.append(f"Unity btn: {short} conf={conf:.3f}")

    def _detect_skills_screen(self, ss, gx, gy, gw, gh):
        self.info_lines.append("Skills screen detected")

        buy_icons = self.vision.find_all_template("buy_skill", ss, 0.82, min_distance=20)
        visible = [(bx, by) for bx, by in buy_icons
                   if gy + int(gh * 0.20) < by < gy + int(gh * 0.95)]

        for bx, by in visible:
            active = self._skill_icon_active(ss, bx, by)
            dot_color = (0, 220, 60) if active else (0, 60, 220)

            name, name_raw = self._ocr_skill_name_at(ss, bx, by, gx, gw, gh, gy)
            cost = self._ocr_skill_cost_at(ss, bx, by, gx, gw, gh, gy)
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

        for btn, thr, label in [("learn_btn", 0.72, "learn"), ("confirm_btn", 0.72, "confirm")]:
            pos, conf = self.vision.find_template_conf(btn, ss, thr)
            if pos:
                self.detections.append(dict(
                    type="point", label=f"{label} ({conf:.2f})", color=(0, 255, 128),
                    x=pos[0], y=pos[1], cat="skill"))
                self.info_lines.append(f"  {label}: {pos} conf={conf:.3f}")

        tpl_close_path = Path("templates/skills/btn_close.png")
        if tpl_close_path.exists():
            tpl_close = cv2.imread(str(tpl_close_path))
            gx, gy, gw, gh = self.vision.get_game_rect(ss)
            game = ss[gy:gy+gh, gx:gx+gw]
            if tpl_close is not None and tpl_close.shape[0] <= game.shape[0] and tpl_close.shape[1] <= game.shape[1]:
                res = cv2.matchTemplate(game, tpl_close, cv2.TM_CCOEFF_NORMED)
                _, mv, _, ml = cv2.minMaxLoc(res)
                if mv >= 0.82:
                    cx = gx + ml[0] + tpl_close.shape[1] // 2
                    cy = gy + ml[1] + tpl_close.shape[0] // 2
                    self.detections.append(dict(
                        type="point", label=f"close ({mv:.2f})", color=(255, 200, 0),
                        x=cx, y=cy, cat="skill"))
                    self.info_lines.append(f"  close: ({cx},{cy}) conf={mv:.3f}")
                else:
                    self.info_lines.append(f"  close: not found (best={mv:.3f})")

        for btn, thr, label in [("btn_back", 0.72, "back")]:
            pos, conf = self.vision.find_template_conf(btn, ss, thr)
            if pos:
                self.detections.append(dict(
                    type="point", label=f"{label} ({conf:.2f})", color=(255, 200, 0),
                    x=pos[0], y=pos[1], cat="skill"))
                self.info_lines.append(f"  {label}: {pos} conf={conf:.3f}")

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

    def _ocr_skill_name_at(self, ss: np.ndarray, icon_x: int, icon_y: int,
                            gx: int, gw: int, gh: int, gy: int):
        from scripts.vision.ocr import _ocr_text_raw
        xf = self.vision._aspect_x_factor(gw, gh)
        x1 = gx + int(gw * 0.08 * xf)
        x2 = gx + int(gw * 0.73 * xf)
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
                n_words = set(n.lower().replace("\u25ce", "").replace("\u25cb", "").split())
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

    def _ocr_skill_cost_at(self, ss: np.ndarray, icon_x: int, icon_y: int,
                            gx: int, gw: int, gh: int, gy: int) -> str:
        from scripts.vision.ocr import _ocr_digits
        cost_x1 = max(0, icon_x - int(gw * 0.16))
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
            pos, conf = self.vision.find_template_conf(ew, ss, 0.80)
            if pos:
                short = ew.replace("event_", "").replace("_window", "")
                event_type = short
                self.detections.append(dict(
                    type="point", label=f"ev_{short} ({conf:.2f})",
                    color=COLORS["event_window"],
                    x=pos[0], y=pos[1], cat="event_win"))
                self.info_lines.append(f"Event window: {short} conf={conf:.3f}")
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
        xf = self.vision._aspect_x_factor(gw, gh)
        roi_names = [
            "energy_bar", "support_region", "date_display",
            "event_title", "event_choices", "training_zone", "mood_zone",
        ]
        for name in roi_names:
            r = self.vision._calibration.get(name)
            if r and "x1" in r:
                x1 = gx + int(gw * r["x1"] * xf)
                y1 = gy + int(gh * r["y1"])
                x2 = gx + int(gw * r["x2"] * xf)
                y2 = gy + int(gh * r["y2"])
                self.detections.append(dict(
                    type="rect", label=name, color=COLORS["roi"],
                    x1=x1, y1=y1, x2=x2, y2=y2, cat="roi", dashed=True))

    def render(self):
        self.overlay = self.screenshot.copy()

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
                    _put_label(self.overlay, label, x1 + 4, y1 - 4, col, 0.55, 1)

            elif det["type"] == "point":
                x, y = det["x"], det["y"]
                cv2.circle(self.overlay, (x, y), 16, col, 2)
                cv2.circle(self.overlay, (x, y), 3, col, -1)
                if label:
                    _put_label(self.overlay, label, x + 20, y + 5, col, 0.55, 1)

            elif det["type"] == "hline":
                y = det["y"]
                x1, x2 = det["x1"], det["x2"]
                cv2.line(self.overlay, (x1, y), (x2, y), col, 2)
                if label:
                    _put_label(self.overlay, label, x1 + 4, y - 6, col, 0.55, 1)

            elif det["type"] == "vline":
                x = det["x"]
                y1, y2 = det["y1"], det["y2"]
                for yy in range(y1, y2, 10):
                    cv2.line(self.overlay, (x, yy), (x, min(yy + 5, y2)), col, 1)

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
        output = self.overlay.copy()
        h, w = output.shape[:2]

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.50
        line_h = 20
        text_pad = 6

        gx_r, _, gw_r, _ = self.vision.get_game_rect(self.screenshot)
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
        sub = output[0:panel_h, px1:px2]
        if sub.size > 0:
            output[0:panel_h, px1:px2] = (sub * 0.20).astype(np.uint8)

        y_text = 16
        for line in self.info_lines:
            cv2.putText(output, line, (px1 + text_pad, y_text),
                        font, font_scale, (255, 255, 255), 1, cv2.LINE_AA)
            y_text += line_h

        Path("logs/debug").mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = f"logs/debug/visual_debug_{ts}.png"
        cv2.imwrite(path, output)
        return path

    def diagnose(self):
        ss = self.screenshot
        gx, gy, gw, gh = self.vision.get_game_rect(ss)
        game = ss[gy:gy+gh, gx:gx+gw]

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
                print(f"  Score ON     : {mv_on:.4f}  {'MATCH (>=0.60)' if mv_on >= 0.60 else 'no match (<0.60)'}")
                print(f"")
                print(f"  ROI brightness      : {roi_brightness:.1f}")
                print(f"  Ref brightness      : {ref_brightness:.1f}")
                print(f"  Diff relative       : {brightness_diff:.3f}  (seuil = 0.15)")
                print(f"  Brightness match    : {'OUI -> bouton allume (ON)' if brightness_match else 'NON -> bouton eteint (OFF)'}")
                print(f"")
                print(f"  detect_injury() = {'True => INJURY detecte' if detect_result else 'False => PAS de blessure'}")

                Path("logs/debug").mkdir(parents=True, exist_ok=True)
                if roi.size > 0:
                    cv2.imwrite("logs/debug/infirmary_detected_roi.png", roi)

        print(f"\n{'='*60}")
        tz = self.vision._calibration.get("training_zone", {})
        xf = self.vision._aspect_x_factor(gw, gh)
        tx1 = max(0, gx + int(gw * tz.get("x1", 0) * xf))
        ty1 = max(0, gy + int(gh * tz.get("y1", 0)))
        tx2 = min(ss.shape[1], gx + int(gw * tz.get("x2", 1) * xf))
        ty2 = min(ss.shape[0], gy + int(gh * tz.get("y2", 1)))
        search = ss[ty1:ty2, tx1:tx2]
        print(f"DIAGNOSE — Training zone: ({tx1},{ty1})->({tx2},{ty2}) = {search.shape[1]}x{search.shape[0]}")
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
            status = "MATCH" if max_val >= thresh else "no match"
            print(f"  {tpl_name:25s}  {tw:3d}x{th:3d}  conf={max_val:.4f}  thresh={thresh}  {status}")

            if th <= game.shape[0] and tw <= game.shape[1]:
                res_full = cv2.matchTemplate(game, tpl, cv2.TM_CCOEFF_NORMED)
                _, mv_full, _, ml_full = cv2.minMaxLoc(res_full)
                if mv_full > max_val + 0.05:
                    rel_y = (ml_full[1] + th//2) / gh
                    print(f"    {'':25s}  -> in full game: conf={mv_full:.4f} at rel_y={rel_y:.3f} (OUTSIDE training zone!)")

        bar_info = self.vision._count_support_bars(ss)
        print(f"\nSupport bars (thin gauge): {bar_info['total']}")
        for ys, ye, bt in bar_info['bars']:
            print(f"  y={ys}-{ye} ({ye-ys+1}px) type={bt}")
        print(f"{'='*60}\n")

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

                print(f"\n  Threshold sweep (COLOR):")
                for thr in [0.90, 0.85, 0.80, 0.75, 0.70, 0.65, 0.60, 0.55, 0.50]:
                    hit = mv_c >= thr
                    print(f"    thr={thr:.2f}  {'FOUND' if hit else 'not found'}  (best={mv_c:.4f})")

                Path("logs/debug").mkdir(parents=True, exist_ok=True)
                cv2.imwrite("logs/debug/btn_close_tpl.png", tpl)
                roi = game[ml_c[1]:ml_c[1]+th, ml_c[0]:ml_c[0]+tw]
                cv2.imwrite("logs/debug/btn_close_match_roi.png", roi)
            else:
                print(f"  Template {tw}x{th} is LARGER than game area {gw}x{gh}")
        print(f"{'='*60}\n")

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
            pos, conf = self.vision.find_template_conf(name, ss, thresh)
            status = "MATCH" if pos else "no match"
            found_str = f"  at {pos}" if pos else ""
            print(f"  {name:25s}  conf={conf:.4f} (>={thresh})  {status}{found_str}")
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
        print(f"{'='*60}\n")


class VisualDebugGUI:

    BG        = "#1e1e2e"
    BG_ALT    = "#252538"
    ACCENT    = "#7c6fff"
    ACCENT_HV = "#6a5de0"
    FG        = "#cdd6f4"
    FG_DIM    = "#888ca8"
    GREEN     = "#5a9e57"
    RED       = "#c45c6a"
    BORDER    = "#393952"

    def __init__(self, config_path, screenshot_path=None):
        import ctypes as _ct
        try:
            _ct.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                _ct.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

        self.tool = VisualDebugTool(config_path=config_path, screenshot_path=screenshot_path)
        self._screenshot_path = screenshot_path

        self.root = tk.Tk()
        self.root.title("\u265e Mihono Bourbot \u2014 Visual Debug")
        self.root.configure(bg=self.BG)

        self._apply_icon()
        self._setup_styles()
        self._build_ui()

        self._photo = None
        self._display_scale = 1.0
        self._display_ox = 0
        self._display_oy = 0
        self._capture_mode = False
        self._cal_game_rect_mode = False
        self._cap_start = None
        self._cap_rect = None
        self._windows = []
        self._window_hwnds = {}
        self._busy = False

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        win_w = min(1400, int(sw * 0.80))
        win_h = min(950, int(sh * 0.85))
        x = (sw - win_w) // 2
        y = (sh - win_h) // 2
        self.root.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.root.minsize(900, 600)

        self.root.after(100, self._initial_load)

    def _apply_icon(self):
        ico_path = os.path.join(os.getcwd(), "assets", "logo.ico")
        if not os.path.exists(ico_path):
            return
        try:
            raw = Image.open(ico_path)
            best = raw.copy().convert("RGBA")
            photo = ImageTk.PhotoImage(best.resize((256, 256), Image.LANCZOS))
            self.root.iconphoto(True, photo)
            self._icon_img = photo
        except Exception:
            try:
                self.root.iconbitmap(default=ico_path)
            except Exception:
                pass

    def _setup_styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")

        style.configure(".", background=self.BG, foreground=self.FG,
                         font=("Segoe UI", 10))
        style.configure("TFrame", background=self.BG)
        style.configure("TLabel", background=self.BG, foreground=self.FG,
                         font=("Segoe UI", 10))

        style.configure("TButton", background=self.ACCENT,
                         foreground="#ffffff", font=("Segoe UI Semibold", 10),
                         padding=[12, 5], borderwidth=0)
        style.map("TButton",
                  background=[("active", self.ACCENT_HV), ("pressed", self.ACCENT_HV)],
                  foreground=[("disabled", self.FG_DIM)])

        style.configure("Tool.TButton", background=self.BORDER,
                         foreground=self.FG, font=("Segoe UI", 9),
                         padding=[10, 4], borderwidth=0)
        style.map("Tool.TButton",
                  background=[("active", self.BG_ALT), ("pressed", self.BG_ALT)])

        style.configure("TCombobox", fieldbackground=self.BG_ALT,
                         foreground=self.FG, arrowcolor=self.ACCENT,
                         selectbackground=self.ACCENT)
        style.map("TCombobox",
                  fieldbackground=[("readonly", self.BG_ALT)],
                  selectbackground=[("readonly", self.ACCENT)])

        style.configure("TCheckbutton", background=self.BG_ALT, foreground=self.FG,
                         indicatorcolor=self.BG_ALT, indicatorrelief="flat")
        style.map("TCheckbutton",
                  background=[("active", self.BG_ALT)],
                  indicatorcolor=[("selected", self.ACCENT), ("!selected", self.BG_ALT)])

        style.configure("TScrollbar", background=self.BG_ALT,
                         troughcolor=self.BG, arrowcolor=self.ACCENT)

    def _build_ui(self):
        top = tk.Frame(self.root, bg=self.BG_ALT, padx=10, pady=6)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Window:", background=self.BG_ALT).pack(side=tk.LEFT, padx=(0, 4))

        self._win_var = tk.StringVar()
        self._win_combo = ttk.Combobox(top, textvariable=self._win_var, width=50, state="readonly")
        self._win_combo.pack(side=tk.LEFT, padx=(0, 10))
        self._win_combo.bind("<<ComboboxSelected>>", self._on_window_selected)

        ttk.Button(top, text="\U0001F4F7 Capture", command=self._capture_and_detect).pack(side=tk.LEFT, padx=2)
        ttk.Button(top, text="\U0001F504 Refresh", command=self._refresh_window_list_only).pack(side=tk.LEFT, padx=2)
        ttk.Button(top, text="\U0001F4BE Save", command=self._save).pack(side=tk.LEFT, padx=2)

        main = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg=self.BORDER,
                              sashwidth=5, sashrelief=tk.FLAT)
        main.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        canvas_frame = tk.Frame(main, bg="#000000")
        self._canvas = tk.Canvas(canvas_frame, bg="#0a0a14", highlightthickness=0)
        self._canvas.pack(fill=tk.BOTH, expand=True)
        self._canvas.bind("<Configure>", lambda e: self._update_canvas())
        main.add(canvas_frame, stretch="always")

        info_frame = tk.Frame(main, bg=self.BG_ALT)
        self._info_text = tk.Text(
            info_frame, bg=self.BG_ALT, fg=self.FG,
            font=("Consolas", 10), wrap=tk.WORD,
            state=tk.DISABLED, borderwidth=0, highlightthickness=0,
            insertbackground=self.FG, selectbackground=self.ACCENT,
        )
        info_scroll = ttk.Scrollbar(info_frame, command=self._info_text.yview)
        self._info_text.configure(yscrollcommand=info_scroll.set)
        info_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._info_text.pack(fill=tk.BOTH, expand=True)
        main.add(info_frame, stretch="never", width=380)

        bottom = tk.Frame(self.root, bg=self.BG_ALT, padx=10, pady=6)
        bottom.pack(fill=tk.X)

        ttk.Label(bottom, text="Platform:", background=self.BG_ALT).pack(side=tk.LEFT, padx=(0, 4))
        self._platform_var = tk.StringVar(
            value=self.tool.config.get("platform", "google_play")
        )
        plat_combo = ttk.Combobox(bottom, textvariable=self._platform_var,
                                  values=["google_play", "steam"],
                                  width=12, state="readonly")
        plat_combo.pack(side=tk.LEFT, padx=(0, 12))
        plat_combo.bind("<<ComboboxSelected>>", self._on_platform_changed)

        ttk.Label(bottom, text="Mode:", background=self.BG_ALT).pack(side=tk.LEFT, padx=(0, 4))
        self._mode_var = tk.StringVar(value="all")
        mode_combo = ttk.Combobox(bottom, textvariable=self._mode_var,
                                  values=["all", "detections", "regions"],
                                  width=12, state="readonly")
        mode_combo.pack(side=tk.LEFT, padx=(0, 12))
        mode_combo.bind("<<ComboboxSelected>>", lambda e: self._rerender())

        self._rois_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bottom, text="ROIs", variable=self._rois_var,
                        command=self._toggle_rois, style="TCheckbutton").pack(side=tk.LEFT, padx=(0, 12))

        ttk.Button(bottom, text="Diagnose", command=self._run_diagnose,
                   style="Tool.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="Capture Template", command=self._start_capture_template,
                   style="Tool.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="Calibrate Game Rect", command=self._start_calibrate_game_rect,
                   style="Tool.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="Calibrate Steam", command=self._start_steam_calibration,
                   style="Tool.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="Calibrate Region", command=self._start_region_calibration,
                   style="Tool.TButton").pack(side=tk.LEFT, padx=2)

        self._status_var = tk.StringVar(value="Ready")
        ttk.Label(bottom, textvariable=self._status_var,
                  background=self.BG_ALT, foreground=self.FG_DIM,
                  font=("Segoe UI", 9)).pack(side=tk.RIGHT)

    def _initial_load(self):
        self._refresh_window_list()
        if self._screenshot_path:
            self._load_and_detect()
        else:
            self._status_var.set("Select a window and press Capture (or F5)")

    def _refresh_window_list(self):
        pid = os.getpid()
        windows = CaptureMixin.enumerate_visible_windows(exclude_pid=pid)
        self._windows = windows
        self._window_hwnds = {}
        titles = []
        for hwnd, title in windows:
            display = f"[{hwnd}] {title}"
            titles.append(display)
            self._window_hwnds[display] = hwnd
        self._win_combo["values"] = titles

        game_titles = ["umamusume", "pretty derby", "dmm"]
        saved_title = self.tool.config.get("window_title", "")
        for display, hwnd in self._window_hwnds.items():
            title_lower = display.lower()
            if saved_title and saved_title in display:
                self._win_combo.set(display)
                return
            if any(kw in title_lower for kw in game_titles):
                self._win_combo.set(display)
                return

        if titles:
            self._win_combo.set(titles[0])

    def _refresh_window_list_only(self):
        self._refresh_window_list()
        self._status_var.set("Window list refreshed")

    def _on_window_selected(self, event=None):
        pass

    def _get_selected_hwnd(self):
        sel = self._win_var.get()
        return self._window_hwnds.get(sel)

    def _auto_find_and_capture(self):
        hwnd = self._get_selected_hwnd()
        if hwnd:
            self._do_capture(hwnd)
        else:
            try:
                self.tool.take_or_load_screenshot()
                self._run_detection()
            except Exception as e:
                self._status_var.set(f"Error: {e}")

    def _capture_and_detect(self):
        if self._busy:
            return
        hwnd = self._get_selected_hwnd()
        if not hwnd:
            self._status_var.set("No window selected")
            return
        self._do_capture(hwnd)

    def _do_capture(self, hwnd):
        if self._busy:
            return
        self._set_busy(True, "Capturing...")

        def _work():
            try:
                self.tool.capture_from_hwnd(hwnd)
                self.tool.mode = self._mode_var.get()
                self.tool.show_rois = self._rois_var.get()
                self.tool.detect_all()
                self.tool.render()
            except Exception as e:
                self.root.after(0, lambda: self._set_busy(False, f"Capture error: {e}"))
                return
            self.root.after(0, self._finish_detection)

        threading.Thread(target=_work, daemon=True).start()

    def _load_and_detect(self):
        if self._busy:
            return
        self._set_busy(True, "Loading screenshot...")

        def _work():
            try:
                self.tool.take_or_load_screenshot()
                self.tool.mode = self._mode_var.get()
                self.tool.show_rois = self._rois_var.get()
                self.tool.detect_all()
                self.tool.render()
            except Exception as e:
                self.root.after(0, lambda: self._set_busy(False, f"Error: {e}"))
                return
            self.root.after(0, self._finish_detection)

        threading.Thread(target=_work, daemon=True).start()

    def _run_detection(self):
        if self._busy:
            return
        self._set_busy(True, "Detecting...")

        def _work():
            try:
                self.tool.mode = self._mode_var.get()
                self.tool.show_rois = self._rois_var.get()
                self.tool.detect_all()
                self.tool.render()
            except Exception as e:
                self.root.after(0, lambda: self._set_busy(False, f"Detection error: {e}"))
                return
            self.root.after(0, self._finish_detection)

        threading.Thread(target=_work, daemon=True).start()

    def _finish_detection(self):
        self._update_canvas()
        self._update_info()
        h, w = self.tool.screenshot.shape[:2]
        self._set_busy(
            False,
            f"Screen: {self.tool.screen.value.upper()} | {w}x{h} | "
            f"{len(self.tool.detections)} detections",
        )

    def _set_busy(self, busy, message=""):
        self._busy = busy
        if message:
            self._status_var.set(message)
        self.root.update_idletasks()

    def _rerender(self):
        if self.tool.overlay is None:
            return
        self._run_detection()

    def _toggle_rois(self):
        self._rerender()

    def _update_canvas(self):
        if self.tool.overlay is None:
            return
        self._canvas.update_idletasks()
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        if cw < 10 or ch < 10:
            return

        rgb = cv2.cvtColor(self.tool.overlay, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        img_w, img_h = pil_img.size

        scale = min(cw / img_w, ch / img_h)
        new_w = max(1, int(img_w * scale))
        new_h = max(1, int(img_h * scale))
        pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)

        self._display_scale = scale
        self._display_ox = (cw - new_w) // 2
        self._display_oy = (ch - new_h) // 2

        self._photo = ImageTk.PhotoImage(pil_img)
        self._canvas.delete("all")
        self._canvas.create_image(
            self._display_ox + new_w // 2,
            self._display_oy + new_h // 2,
            anchor=tk.CENTER, image=self._photo,
        )

    def _update_info(self):
        self._info_text.configure(state=tk.NORMAL)
        self._info_text.delete("1.0", tk.END)
        for line in self.tool.info_lines:
            self._info_text.insert(tk.END, line + "\n")
        self._info_text.configure(state=tk.DISABLED)

    def _save(self):
        if self.tool.overlay is None:
            self._status_var.set("Nothing to save")
            return
        path = self.tool.save_annotated()
        self._status_var.set(f"Saved: {path}")

    def _run_diagnose(self):
        if self.tool.screenshot is None:
            self._status_var.set("No screenshot loaded")
            return
        if self._busy:
            return
        self._set_busy(True, "Running diagnose...")

        def _work():
            old_stdout = sys.stdout
            sys.stdout = buffer = io.StringIO()
            try:
                self.tool.diagnose()
            finally:
                sys.stdout = old_stdout
            output = buffer.getvalue()
            self.root.after(0, lambda: self._show_diagnose_result(output))

        threading.Thread(target=_work, daemon=True).start()

    def _show_diagnose_result(self, output):
        self._set_busy(False, "Diagnose complete")

        diag_win = tk.Toplevel(self.root)
        diag_win.title("Diagnose Output")
        diag_win.configure(bg=self.BG)
        diag_win.geometry("700x600")

        text = tk.Text(diag_win, bg=self.BG_ALT, fg=self.FG,
                       font=("Consolas", 10), wrap=tk.WORD,
                       borderwidth=0, highlightthickness=0)
        scroll = ttk.Scrollbar(diag_win, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(tk.END, output)
        text.configure(state=tk.DISABLED)

    def _start_capture_template(self):
        if self.tool.screenshot is None:
            self._status_var.set("No screenshot loaded")
            return
        self._show_raw_for_calibration()
        self._capture_mode = True
        self._cap_start = None
        self._cap_rect = None
        self._canvas.config(cursor="crosshair")
        self._canvas.bind("<ButtonPress-1>", self._on_cap_press)
        self._canvas.bind("<B1-Motion>", self._on_cap_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_cap_release)
        self._status_var.set("Draw a rectangle on the image to capture a template...")

    def _end_capture_mode(self):
        self._capture_mode = False
        self._cal_game_rect_mode = False
        self._canvas.config(cursor="")
        self._canvas.unbind("<ButtonPress-1>")
        self._canvas.unbind("<B1-Motion>")
        self._canvas.unbind("<ButtonRelease-1>")
        if self._cap_rect:
            self._canvas.delete(self._cap_rect)
            self._cap_rect = None

    def _on_cap_press(self, event):
        self._cap_start = (event.x, event.y)
        if self._cap_rect:
            self._canvas.delete(self._cap_rect)

    def _on_cap_drag(self, event):
        if self._cap_start is None:
            return
        if self._cap_rect:
            self._canvas.delete(self._cap_rect)
        x1, y1 = self._cap_start
        self._cap_rect = self._canvas.create_rectangle(
            x1, y1, event.x, event.y,
            outline=self.ACCENT, width=2, dash=(6, 4),
        )

    def _on_cap_release(self, event):
        if self._cap_start is None:
            self._end_capture_mode()
            return

        cx1, cy1 = self._cap_start
        cx2, cy2 = event.x, event.y

        ix1 = int((min(cx1, cx2) - self._display_ox) / self._display_scale)
        iy1 = int((min(cy1, cy2) - self._display_oy) / self._display_scale)
        ix2 = int((max(cx1, cx2) - self._display_ox) / self._display_scale)
        iy2 = int((max(cy1, cy2) - self._display_oy) / self._display_scale)

        ih, iw = self.tool.screenshot.shape[:2]
        ix1 = max(0, min(iw, ix1))
        iy1 = max(0, min(ih, iy1))
        ix2 = max(0, min(iw, ix2))
        iy2 = max(0, min(ih, iy2))

        self._end_capture_mode()

        if ix2 - ix1 < 5 or iy2 - iy1 < 5:
            self._status_var.set("Selection too small, cancelled")
            return

        crop = self.tool.screenshot[iy1:iy2, ix1:ix2]

        name = simpledialog.askstring(
            "Capture Template",
            f"Template name ({ix2-ix1}x{iy2-iy1} px):",
            parent=self.root,
        )
        if not name:
            self._status_var.set("Cancelled")
            return

        path = f"templates/{name}.png"
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(path, crop)
        if name in self.tool.vision.templates:
            del self.tool.vision.templates[name]
        self.tool.vision._template_paths[name] = Path(path)
        if name in self.tool.vision._raw_templates:
            del self.tool.vision._raw_templates[name]
        if "anchor" in name:
            self.tool.vision._auto_game_rect_cache = None
        self._status_var.set(f"Saved template: {path} ({ix2-ix1}x{iy2-iy1})")

    def _on_platform_changed(self, event=None):
        new_platform = self._platform_var.get()
        self.tool.config["platform"] = new_platform
        self.tool.vision.config["platform"] = new_platform
        self.tool.vision._auto_game_rect_cache = None
        self.tool.vision._calibration = self.tool.vision._load_calibration()
        if self.tool.screenshot is not None:
            self._run_detection()
        else:
            self._status_var.set(f"Platform: {new_platform}")

    _STEAM_CAL_STEPS = [
        ("energy_bar",    "Draw a rectangle around the ENERGY BAR (the colored bar, not the text)"),
        ("mood_zone",     "Draw a rectangle around the MOOD ICON (the small face icon to the right of energy)"),
        ("stat_speed",    "Draw a rectangle around the SPEED stat value (e.g. '89')"),
        ("stat_stamina",  "Draw a rectangle around the STAMINA stat value (e.g. '112')"),
        ("stat_power",    "Draw a rectangle around the POWER stat value (e.g. '89')"),
        ("stat_guts",     "Draw a rectangle around the GUTS stat value (e.g. '100')"),
        ("stat_wit",      "Draw a rectangle around the WIT stat value (e.g. '95')"),
        ("btn_training",  "Draw a rectangle around the TRAIN button"),
        ("btn_rest",      "Draw a rectangle around the REST button"),
        ("btn_recreation","Draw a rectangle around the RECREATION button"),
        ("btn_races",     "Draw a rectangle around the RACES button"),
        ("btn_infirmary", "Draw a rectangle the INFIRMARY button (bottom-left, the nurse icon)"),
    ]

    def _start_steam_calibration(self):
        if self.tool.screenshot is None:
            self._status_var.set("Take a screenshot first")
            return
        if self._platform_var.get() != "steam":
            self._platform_var.set("steam")
            self._on_platform_changed()
        self._steam_cal_data = {}
        self._steam_cal_index = 0
        self._steam_cal_active = True
        self._show_raw_for_calibration()
        self.root.bind("<Escape>", self._cancel_steam_calibration)
        self._begin_steam_cal_step()

    def _begin_steam_cal_step(self):
        if self._steam_cal_index >= len(self._STEAM_CAL_STEPS):
            self._finish_steam_calibration()
            return
        key, instruction = self._STEAM_CAL_STEPS[self._steam_cal_index]
        step = self._steam_cal_index + 1
        total = len(self._STEAM_CAL_STEPS)
        self._capture_mode = True
        self._cap_start = None
        self._cap_rect = None
        self._canvas.config(cursor="crosshair")
        self._canvas.unbind("<ButtonPress-1>")
        self._canvas.unbind("<B1-Motion>")
        self._canvas.unbind("<ButtonRelease-1>")
        self._canvas.bind("<ButtonPress-1>", self._on_cap_press)
        self._canvas.bind("<B1-Motion>", self._on_cap_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_steam_cal_release)
        self._status_var.set(f"[{step}/{total}] {instruction}")

    def _on_steam_cal_release(self, event):
        if self._cap_start is None:
            return
        cx1, cy1 = self._cap_start
        cx2, cy2 = event.x, event.y
        ix1 = int((min(cx1, cx2) - self._display_ox) / self._display_scale)
        iy1 = int((min(cy1, cy2) - self._display_oy) / self._display_scale)
        ix2 = int((max(cx1, cx2) - self._display_ox) / self._display_scale)
        iy2 = int((max(cy1, cy2) - self._display_oy) / self._display_scale)
        ss = self.tool.screenshot
        ih, iw = ss.shape[:2]
        ix1 = max(0, min(iw, ix1))
        iy1 = max(0, min(ih, iy1))
        ix2 = max(0, min(iw, ix2))
        iy2 = max(0, min(ih, iy2))
        if self._cap_rect:
            self._canvas.delete(self._cap_rect)
            self._cap_rect = None
        self._cap_start = None
        if ix2 - ix1 < 3 or iy2 - iy1 < 3:
            self._status_var.set("Too small — try again")
            return
        gx, gy, gw, gh = self.tool.vision.get_game_rect(ss)
        key = self._STEAM_CAL_STEPS[self._steam_cal_index][0]
        ratios = {
            "x1": round((ix1 - gx) / max(1, gw), 4),
            "y1": round((iy1 - gy) / max(1, gh), 4),
            "x2": round((ix2 - gx) / max(1, gw), 4),
            "y2": round((iy2 - gy) / max(1, gh), 4),
        }
        self._steam_cal_data[key] = ratios
        step = self._steam_cal_index + 1
        total = len(self._STEAM_CAL_STEPS)
        short = key.replace("btn_", "").replace("stat_", "")
        self._canvas.create_rectangle(
            cx1 if cx1 < event.x else event.x,
            cy1 if cy1 < event.y else event.y,
            event.x if cx1 < event.x else cx1,
            event.y if cy1 < event.y else cy1,
            outline="#00FF00", width=2, tags="steam_cal_done"
        )
        self.root.after(100, self._steam_cal_advance)

    def _steam_cal_advance(self):
        self._steam_cal_index += 1
        self._begin_steam_cal_step()

    def _cancel_steam_calibration(self, event=None):
        self._end_capture_mode()
        self._steam_cal_active = False
        self._canvas.delete("steam_cal_done")
        self.root.unbind("<Escape>")
        done = self._steam_cal_index
        self._status_var.set(f"Steam calibration cancelled ({done} of {len(self._STEAM_CAL_STEPS)} done)")

    def _finish_steam_calibration(self):
        self._end_capture_mode()
        self._steam_cal_active = False
        self._canvas.delete("steam_cal_done")
        self.root.unbind("<Escape>")

        steam_path = Path("config", "calibration_steam.json")
        existing = {}
        if steam_path.exists():
            try:
                with open(steam_path, encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                pass
        existing.update(self._steam_cal_data)
        with open(steam_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)

        self.tool.vision._calibration.update(self._steam_cal_data)

        base_path = Path("config", "calibration.json")
        base_cal = {}
        if base_path.exists():
            try:
                with open(base_path, encoding="utf-8") as f:
                    base_cal = json.load(f)
            except Exception:
                pass

        gp_rect = base_cal.get("game_rect", {})
        steam_rect = base_cal.get("steam_game_rect", {})
        x_ratio = None
        x_offset = None
        if gp_rect and steam_rect and "x1" in gp_rect and "x1" in steam_rect:
            gp_w = gp_rect["x2"] - gp_rect["x1"]
            steam_w = steam_rect["x2"] - steam_rect["x1"]
            if steam_w > 0 and gp_w > 0:
                x_ratio = gp_w / steam_w
                x_offset = (1.0 - x_ratio) / 2.0

        lines = [f"Steam calibration saved ({len(self._steam_cal_data)} regions):\n"]
        errors = []
        for key, steam_r in sorted(self._steam_cal_data.items()):
            base_r = base_cal.get(key)
            line = f"  {key}: x1={steam_r['x1']:.4f} y1={steam_r['y1']:.4f} x2={steam_r['x2']:.4f} y2={steam_r['y2']:.4f}"
            if base_r and "x1" in base_r and x_ratio is not None:
                pred_x1 = base_r["x1"] * x_ratio + x_offset
                pred_x2 = base_r["x2"] * x_ratio + x_offset
                err_x1 = abs(steam_r["x1"] - pred_x1)
                err_x2 = abs(steam_r["x2"] - pred_x2)
                err_y1 = abs(steam_r["y1"] - base_r["y1"])
                err_y2 = abs(steam_r["y2"] - base_r["y2"])
                errors.extend([err_x1, err_x2])
                line += (
                    f"\n    predicted: x1={pred_x1:.4f} x2={pred_x2:.4f} "
                    f"| err: x1={err_x1:.4f} x2={err_x2:.4f} y1={err_y1:.4f} y2={err_y2:.4f}"
                )
            elif base_r is None:
                line += "  [no GP baseline]"
            lines.append(line)

        if x_ratio is not None:
            lines.append(f"\n{'='*60}")
            lines.append(f"Auto-transform formula:")
            lines.append(f"  steam_x = gp_x * {x_ratio:.4f} + {x_offset:.4f}")
            lines.append(f"  steam_y = gp_y (unchanged)")
            lines.append(f"  (GP game={gp_rect['x2']-gp_rect['x1']:.4f}w  Steam game={steam_rect['x2']-steam_rect['x1']:.4f}w)")
            if errors:
                avg_err = sum(errors) / len(errors)
                max_err = max(errors)
                lines.append(f"  Prediction accuracy: avg_err={avg_err:.4f} max_err={max_err:.4f}")
            remaining = set(base_cal.keys()) - set(self._steam_cal_data.keys()) - {"game_rect", "steam_game_rect"}
            remaining_rects = [k for k in remaining if isinstance(base_cal.get(k), dict) and ("x1" in base_cal[k] or "x" in base_cal[k])]
            lines.append(f"  {len(remaining_rects)} remaining regions will be auto-transformed at load time")
            lines.append(f"  {len(self._steam_cal_data)} regions use manual calibration (overrides)")

        report = "\n".join(lines)
        print(report)

        report_win = tk.Toplevel(self.root)
        report_win.title("Steam Calibration Report")
        report_win.geometry("700x500")
        report_win.configure(bg=self.BG)
        text = tk.Text(report_win, wrap=tk.WORD, bg=self.BG, fg=self.FG,
                       font=("Consolas", 10), borderwidth=0, highlightthickness=0)
        scroll = ttk.Scrollbar(report_win, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(tk.END, report)
        text.configure(state=tk.DISABLED)

        self._status_var.set(f"Steam calibration done — {len(self._steam_cal_data)} regions saved")

        self.tool.vision._calibration = self.tool.vision._load_calibration()

        if self.tool.screenshot is not None:
            self._run_detection()

    def _start_region_calibration(self):
        if self.tool.screenshot is None:
            self._status_var.set("Take a screenshot first")
            return
        cal = self.tool.vision._calibration
        region_keys = sorted(
            k for k, v in cal.items()
            if isinstance(v, dict) and ("x1" in v or "x" in v)
            and k not in ("game_rect", "steam_game_rect")
        )
        if not region_keys:
            self._status_var.set("No calibration regions found")
            return
        popup = tk.Toplevel(self.root)
        popup.title("Calibrate Region")
        popup.configure(bg=self.BG)
        popup.geometry("350x450")
        popup.transient(self.root)
        popup.grab_set()
        tk.Label(popup, text="Select a region to recalibrate:",
                 bg=self.BG, fg=self.FG, font=("Segoe UI", 11)).pack(pady=(10, 5))
        listbox = tk.Listbox(popup, bg=self.BG_ALT, fg=self.FG,
                             selectbackground=self.ACCENT,
                             font=("Consolas", 10), borderwidth=0)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        for k in region_keys:
            listbox.insert(tk.END, k)
        def on_select():
            sel = listbox.curselection()
            if not sel:
                return
            key = region_keys[sel[0]]
            popup.destroy()
            self._begin_single_region_cal(key)
        ttk.Button(popup, text="Calibrate", command=on_select,
                   style="Tool.TButton").pack(pady=(5, 10))
        listbox.bind("<Double-1>", lambda e: on_select())

    def _begin_single_region_cal(self, key):
        self._single_cal_key = key
        self._show_raw_for_calibration()
        self._capture_mode = True
        self._cap_start = None
        self._cap_rect = None
        self._canvas.config(cursor="crosshair")
        self._canvas.bind("<ButtonPress-1>", self._on_cap_press)
        self._canvas.bind("<B1-Motion>", self._on_cap_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_single_region_release)
        self.root.bind("<Escape>", self._cancel_single_region_cal)
        self._status_var.set(f"Draw a rectangle for: {key}")

    def _on_single_region_release(self, event):
        if self._cap_start is None:
            return
        cx1, cy1 = self._cap_start
        cx2, cy2 = event.x, event.y
        ix1 = int((min(cx1, cx2) - self._display_ox) / self._display_scale)
        iy1 = int((min(cy1, cy2) - self._display_oy) / self._display_scale)
        ix2 = int((max(cx1, cx2) - self._display_ox) / self._display_scale)
        iy2 = int((max(cy1, cy2) - self._display_oy) / self._display_scale)
        ss = self.tool.screenshot
        ih, iw = ss.shape[:2]
        ix1 = max(0, min(iw, ix1))
        iy1 = max(0, min(ih, iy1))
        ix2 = max(0, min(iw, ix2))
        iy2 = max(0, min(ih, iy2))
        if self._cap_rect:
            self._canvas.delete(self._cap_rect)
            self._cap_rect = None
        self._cap_start = None
        if ix2 - ix1 < 3 or iy2 - iy1 < 3:
            self._status_var.set("Too small — try again")
            return
        gx, gy, gw, gh = self.tool.vision.get_game_rect(ss)
        key = self._single_cal_key
        ratios = {
            "x1": round((ix1 - gx) / max(1, gw), 4),
            "y1": round((iy1 - gy) / max(1, gh), 4),
            "x2": round((ix2 - gx) / max(1, gw), 4),
            "y2": round((iy2 - gy) / max(1, gh), 4),
        }
        self._end_capture_mode()
        self.root.unbind("<Escape>")
        platform = self._platform_var.get()
        if platform == "steam":
            steam_path = Path("config", "calibration_steam.json")
            existing = {}
            if steam_path.exists():
                try:
                    with open(steam_path, encoding="utf-8") as f:
                        existing = json.load(f)
                except Exception:
                    pass
            existing[key] = ratios
            with open(steam_path, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)
        else:
            cal_path = Path("config", "calibration.json")
            existing = {}
            if cal_path.exists():
                try:
                    with open(cal_path, encoding="utf-8") as f:
                        existing = json.load(f)
                except Exception:
                    pass
            existing[key] = ratios
            with open(cal_path, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)
        self.tool.vision._calibration = self.tool.vision._load_calibration()
        self._status_var.set(
            f"Saved {key}: x1={ratios['x1']:.4f} y1={ratios['y1']:.4f} "
            f"x2={ratios['x2']:.4f} y2={ratios['y2']:.4f} [{platform}]"
        )
        self._run_detection()

    def _cancel_single_region_cal(self, event=None):
        self._end_capture_mode()
        self.root.unbind("<Escape>")
        self._status_var.set("Region calibration cancelled")
        self._run_detection()

    def _show_raw_for_calibration(self):
        if self.tool.screenshot is None:
            return
        rgb = cv2.cvtColor(self.tool.screenshot, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        self._canvas.update_idletasks()
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        if cw < 10 or ch < 10:
            return
        img_w, img_h = pil_img.size
        scale = min(cw / img_w, ch / img_h)
        new_w = max(1, int(img_w * scale))
        new_h = max(1, int(img_h * scale))
        pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)
        self._display_scale = scale
        ox = (cw - new_w) // 2
        oy = (ch - new_h) // 2
        self._display_ox = ox
        self._display_oy = oy
        self._photo = ImageTk.PhotoImage(pil_img)
        self._canvas.delete("all")
        self._canvas.create_image(ox, oy, anchor=tk.NW, image=self._photo)

    def _start_calibrate_game_rect(self):
        if self.tool.screenshot is None:
            self._status_var.set("No screenshot loaded")
            return
        self._show_raw_for_calibration()
        self._capture_mode = True
        self._cal_game_rect_mode = True
        self._cap_start = None
        self._cap_rect = None
        self._canvas.config(cursor="crosshair")
        self._canvas.bind("<ButtonPress-1>", self._on_cap_press)
        self._canvas.bind("<B1-Motion>", self._on_cap_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_cal_rect_release)
        self._status_var.set("Draw the game area rectangle on the image...")

    def _on_cal_rect_release(self, event):
        if self._cap_start is None:
            self._end_capture_mode()
            return

        cx1, cy1 = self._cap_start
        cx2, cy2 = event.x, event.y

        ix1 = int((min(cx1, cx2) - self._display_ox) / self._display_scale)
        iy1 = int((min(cy1, cy2) - self._display_oy) / self._display_scale)
        ix2 = int((max(cx1, cx2) - self._display_ox) / self._display_scale)
        iy2 = int((max(cy1, cy2) - self._display_oy) / self._display_scale)

        ih, iw = self.tool.screenshot.shape[:2]
        ix1 = max(0, min(iw, ix1))
        iy1 = max(0, min(ih, iy1))
        ix2 = max(0, min(iw, ix2))
        iy2 = max(0, min(ih, iy2))

        self._end_capture_mode()
        self._cal_game_rect_mode = False

        if ix2 - ix1 < 20 or iy2 - iy1 < 20:
            self._status_var.set("Selection too small, cancelled")
            return

        ratios = {
            "x1": round(ix1 / iw, 4),
            "y1": round(iy1 / ih, 4),
            "x2": round(ix2 / iw, 4),
            "y2": round(iy2 / ih, 4),
        }

        platform = self._platform_var.get()
        cal_key = "steam_game_rect" if platform == "steam" else "game_rect"

        cal_path = Path("config", "calibration.json")
        cal_data = {}
        if cal_path.exists():
            try:
                with open(cal_path, encoding="utf-8") as f:
                    cal_data = json.load(f)
            except Exception:
                pass
        cal_data[cal_key] = ratios
        with open(cal_path, "w", encoding="utf-8") as f:
            json.dump(cal_data, f, indent=2, ensure_ascii=False)

        self.tool.vision._calibration[cal_key] = ratios
        self.tool.vision._auto_game_rect_cache = None

        result_w = ix2 - ix1
        result_h = iy2 - iy1
        info = (
            f"Saved {cal_key}: x1={ratios['x1']}, y1={ratios['y1']}, "
            f"x2={ratios['x2']}, y2={ratios['y2']} "
            f"({result_w}x{result_h} px at {iw}x{ih})"
        )
        self._status_var.set(info)

        if self.tool.screenshot is not None:
            self._run_detection()

    def run(self):
        self.root.mainloop()


def main():
    parser = argparse.ArgumentParser(description="Visual Debug Tool")
    parser.add_argument("--screenshot", type=str, default=None)
    parser.add_argument("--config", type=str, default=os.path.join("config", "config.json"))
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()

    if args.save:
        tool = VisualDebugTool(config_path=args.config, screenshot_path=args.screenshot)
        tool.take_or_load_screenshot()
        tool.detect_all()
        tool.render()
        path = tool.save_annotated()
        print(f"Saved: {path}")
        for line in tool.info_lines:
            print(f"  {line}")
    else:
        gui = VisualDebugGUI(config_path=args.config, screenshot_path=args.screenshot)
        gui.run()


if __name__ == "__main__":
    main()
