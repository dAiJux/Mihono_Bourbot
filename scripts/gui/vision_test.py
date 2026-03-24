import json
import os
import threading
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from difflib import SequenceMatcher

class VisionTestDialog(tk.Toplevel):

    _COLORS = {
        "game_rect":  (0, 255, 0),
        "button":     (128, 255, 128),
        "stat":       (0, 180, 255),
        "energy":     (0, 200, 255),
        "mood":       (255, 128, 0),
        "event":      (200, 100, 255),
        "warning":    (0, 0, 255),
        "skill_buy":  (0, 220, 60),
        "skill_lock": (0, 60, 220),
    }

    _MAIN_BUTTONS = [
        "btn_training", "btn_rest", "btn_recreation", "btn_races",
        "btn_rest_summer", "btn_skills",
    ]
    _GENERIC_BUTTONS = [
        "btn_confirm", "btn_ok", "btn_close", "btn_cancel",
        "btn_skip", "btn_tap", "btn_next", "btn_back",
        "btn_race_confirm", "btn_race_start", "btn_race_next_finish",
        "btn_inspiration", "btn_claw_machine", "btn_try_again",
    ]
    _RACE_BUTTONS = [
        "race_view_results_on", "race_view_results_off",
        "btn_race_start", "btn_race_start_ura", "btn_race_launch",
        "btn_change_strategy", "btn_skip",
    ]
    _STRATEGY_TEMPLATES = [
        "strategy_end", "strategy_late", "strategy_pace", "strategy_front",
    ]
    _UNITY_BUTTONS = [
        "btn_unity_launch", "btn_select_opponent", "btn_begin_showdown",
        "btn_see_unity_results", "btn_next_unity", "btn_launch_final_unity",
    ]

    def __init__(self, parent, config_path):
        super().__init__(parent)
        self.title("Vision Test")
        self.configure(bg="#1e1e2e")
        self.minsize(800, 500)

        with open(config_path, encoding="utf-8") as f:
            self._config = json.load(f)
        self._config_path = config_path

        self._vision = None
        self._photo = None
        self._busy = False

        top_bar = tk.Frame(self, bg="#1e1e2e")
        top_bar.pack(fill="x", padx=8, pady=(8, 0))

        self._refresh_btn = tk.Button(
            top_bar, text="\u21bb  Refresh", font=("Segoe UI", 10),
            bg="#7c6fff", fg="white", activebackground="#6a5de0",
            relief="flat", padx=12, pady=4, command=self._on_refresh,
        )
        self._refresh_btn.pack(side="left")

        self._status_var = tk.StringVar(value="Click Refresh to capture a screenshot")
        tk.Label(
            top_bar, textvariable=self._status_var,
            bg="#1e1e2e", fg="#888ca8", font=("Segoe UI", 9),
        ).pack(side="left", padx=12)

        body = tk.PanedWindow(
            self, orient="horizontal", bg="#252538",
            sashwidth=4, sashrelief="flat",
        )
        body.pack(fill="both", expand=True, padx=8, pady=8)

        img_frame = tk.Frame(body, bg="#1e1e2e")
        body.add(img_frame, stretch="always")

        self._canvas = tk.Canvas(img_frame, bg="#1e1e2e", highlightthickness=0)
        self._canvas.pack(fill="both", expand=True)

        info_frame = tk.Frame(body, bg="#1e1e2e", width=320)
        body.add(info_frame, stretch="never")

        self._info_text = tk.Text(
            info_frame, bg="#1e1e2e", fg="#cdd6f4",
            font=("Consolas", 9), wrap="word", state="disabled",
            relief="flat", borderwidth=0, padx=6, pady=6,
        )
        scroll = ttk.Scrollbar(info_frame, command=self._info_text.yview)
        self._info_text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self._info_text.pack(fill="both", expand=True)

        self._info_text.tag_configure("header", foreground="#7c6fff", font=("Consolas", 10, "bold"))
        self._info_text.tag_configure("ok", foreground="#5a9e57")
        self._info_text.tag_configure("warn", foreground="#b89b4a")
        self._info_text.tag_configure("bad", foreground="#c45c6a")

        self._canvas.bind("<Configure>", lambda e: self._redraw_image())

        self.after(200, self._on_refresh)

    def _init_vision(self):
        if self._vision is not None:
            return
        from scripts.vision import VisionModule
        self._vision = VisionModule(self._config)
        self._vision.find_game_window()

    def _on_refresh(self):
        if self._busy:
            return
        self._busy = True
        self._refresh_btn.configure(state="disabled")
        self._status_var.set("Capturing...")
        threading.Thread(target=self._capture_and_analyse, daemon=True).start()

    def _capture_and_analyse(self):
        try:
            import cv2
            import numpy as np
            self._init_vision()
            if not self._vision.game_hwnd:
                self._vision.find_game_window()
            if not self._vision.game_hwnd:
                self.after(0, lambda: self._show_error("Game window not found"))
                return

            ss = self._vision.take_screenshot()
            gx, gy, gw, gh = self._vision.get_game_rect(ss)
            info = []
            detections = []

            from scripts.models import GameScreen
            screen = self._vision.detect_screen(ss)
            info.append(("SCREEN", f"{screen.value.upper()}", "header"))

            platform = self._config.get("platform", "google_play")
            info.append(("", f"Platform: {platform}", None))
            info.append(("", f"Game area: {gw}x{gh} at ({gx},{gy})", None))

            detections.append(("rect", self._COLORS["game_rect"], gx, gy, gx + gw, gy + gh, "Game"))

            if screen in (GameScreen.MAIN, GameScreen.TRAINING,
                          GameScreen.INSUFFICIENT_FANS, GameScreen.SCHEDULED_RACE_POPUP):
                energy = self._vision.read_energy_percentage(ss)
                tag = "ok" if energy >= 50 else ("warn" if energy >= 30 else "bad")
                info.append(("ENERGY", f"{energy:.0f}%", tag))

                eb = self._vision._calibration.get("energy_bar", {})
                if eb:
                    xf = self._vision._aspect_x_factor(gw, gh)
                    ey1 = gy + int(gh * eb.get("y1", 0.082))
                    ey2 = gy + int(gh * eb.get("y2", 0.098))
                    ex1 = gx + int(gw * eb.get("x1", 0.33) * xf)
                    ex2 = gx + int(gw * eb.get("x2", 0.69) * xf)
                    detections.append(("rect", self._COLORS["energy"], ex1, ey1, ex2, ey2, f"Energy {energy:.0f}%"))

                mood = self._vision.detect_mood(ss)
                mtag = "ok" if mood in ("great", "good") else ("warn" if mood == "normal" else "bad")
                info.append(("MOOD", mood, mtag))

                mz = self._vision._calibration.get("mood_zone", {})
                if mz and mood != "unknown":
                    mx = gx + int(gw * (mz.get("x1", 0.70) + mz.get("x2", 0.90)) / 2)
                    my = gy + int(gh * (mz.get("y1", 0.095) + mz.get("y2", 0.155)) / 2)
                    detections.append(("dot", self._COLORS["mood"], mx, my, f"Mood: {mood}"))

            if screen in (GameScreen.MAIN, GameScreen.TRAINING):
                stats = self._vision.read_stats(ss)
                if stats:
                    info.append(("STATS", "", "header"))
                    for name in ("speed", "stamina", "power", "guts", "wit"):
                        val = stats.get(name, "?")
                        info.append(("", f"  {name.title()}: {val}", None))

                    for name in ("speed", "stamina", "power", "guts", "wit"):
                        cal = self._vision._calibration.get(f"stat_{name}")
                        if cal and "x1" in cal and name in stats:
                            sx1 = max(0, gx + int(gw * cal["x1"]))
                            sx2 = min(ss.shape[1], gx + int(gw * cal["x2"]))
                            sy1 = gy + int(gh * 0.665)
                            sy2 = gy + int(gh * 0.690)
                            detections.append(("rect", self._COLORS["stat"], sx1, sy1, sx2, sy2,
                                               f"{name[:3].upper()} {stats.get(name, '?')}"))

                has_injury = self._vision.detect_injury(ss)
                if has_injury:
                    info.append(("INJURY", "Detected!", "bad"))

            if screen in (GameScreen.MAIN, GameScreen.UNKNOWN):
                info.append(("BUTTONS", "", "header"))
                for btn in self._MAIN_BUTTONS:
                    pos, conf = self._vision.find_template_conf(btn, ss, 0.70)
                    if pos and gx <= pos[0] <= gx + gw:
                        short = btn.replace("btn_", "")
                        pct = int(conf * 100)
                        info.append(("", f"  {short} ({pct}%)", "ok"))
                        detections.append(("dot", self._COLORS["button"], pos[0], pos[1], f"{short} {pct}%"))

            if screen == GameScreen.TRAINING:
                info.append(("TRAINING", "", "header"))
                opts = self._vision.get_training_options(ss)
                for name, pos in opts.items():
                    if pos:
                        info.append(("", f"  {name.title()} : visible", "ok"))
                        detections.append(("dot", self._COLORS["button"], pos[0], pos[1], name.title()))
                    else:
                        info.append(("", f"  {name.title()} : not visible", "warn"))
                try:
                    abbrevs = {"speed": "Spe", "stamina": "Sta", "power": "Pow",
                               "guts": "Gut", "wit": "Wit", "pal": "PAL"}
                    card_types = self._vision.detect_card_types_with_pal(ss)
                    if card_types:
                        ct_str = " | ".join(abbrevs.get(ct, ct) for ct in card_types)
                        info.append(("", f"  Card types : {ct_str}", None))
                    bar_info = self._vision._count_support_bars(ss)
                    if bar_info["bars"]:
                        bar_str = ", ".join(t for _, _, t in bar_info["bars"])
                        info.append(("", f"  Support bars : {bar_info['total']} ({bar_str})", None))
                    levels = self._vision.count_support_friendship_leveled(ss)
                    parts = []
                    if levels["partial"]:
                        parts.append(f"partial={levels['partial']}")
                    if levels["orange_plus"]:
                        parts.append(f"orange+={levels['orange_plus']}")
                    if levels["pal_orange"]:
                        parts.append(f"pal_orange={levels['pal_orange']}")
                    if levels["pal"]:
                        parts.append("pal=yes")
                    if parts:
                        info.append(("", f"  Friendship : {' '.join(parts)}", None))
                    else:
                        info.append(("", "  Friendship : none detected", "warn"))
                except Exception:
                    pass
                rainbow_count = self._vision.detect_rainbow_training(ss)
                bursts = self._vision.detect_burst_training(ss)
                if rainbow_count:
                    info.append(("", f"  Rainbow : {rainbow_count}", "ok"))
                if bursts["white"]:
                    info.append(("", f"  White burst : {len(bursts['white'])}", None))
                if bursts["blue"]:
                    info.append(("", f"  Blue burst : {len(bursts['blue'])}", None))

            if screen == GameScreen.EVENT:
                event_type = self._vision.detect_event_type(ss)
                info.append(("EVENT", f"Type : {event_type or 'unknown'}", "header"))
                try:
                    title = self._vision.read_event_title(ss)
                    if title:
                        info.append(("", f"  Title : {title}", None))
                except Exception:
                    title = None
                ec = self._vision._calibration.get("event_choices", {})
                choice_y_min = gy + int(gh * ec.get("y1", 0.35))
                choice_y_max = gy + int(gh * ec.get("y2", 0.85))
                raw_choices = self._vision.find_all_template("event_choice", ss, 0.75, min_distance=30)
                choices = sorted(
                    [c for c in raw_choices if gx <= c[0] <= gx + gw and choice_y_min <= c[1] <= choice_y_max],
                    key=lambda p: p[1],
                )
                if choices:
                    info.append(("", f"  {len(choices)} choice(s)", None))
                    try:
                        choice_texts = self._vision.read_choice_texts(ss, choices)
                        for i, ct in enumerate(choice_texts):
                            info.append(("", f"    {i+1}. {ct}", None))
                            detections.append(("dot", self._COLORS["button"], choices[i][0], choices[i][1], f"C{i+1}"))
                    except Exception:
                        pass
                else:
                    info.append(("", "  No choices detected", "warn"))
                try:
                    if title:
                        self._show_event_db_match(info, title)
                except Exception:
                    pass

            if screen == GameScreen.SKILL_SELECT:
                info.append(("SKILLS", "", "header"))
                try:
                    buy_icons = self._vision.find_all_template("buy_skill", ss, 0.82, min_distance=20)
                    visible = [(bx, by) for bx, by in buy_icons
                               if gy + int(gh * 0.20) < by < gy + int(gh * 0.95)]
                    info.append(("", f"  {len(visible)} visible skill(s)", None))
                    for bx, by in visible:
                        active = self._skill_icon_active(ss, bx, by)
                        name = self._ocr_skill_name(ss, bx, by, gx, gw, gh, gy)
                        cost = self._ocr_skill_cost(ss, bx, by, gx, gw, gh, gy)
                        state = "BUYABLE" if active else "locked"
                        tag = "ok" if active else "warn"
                        label = f"  {name} [{cost} SP] — {state}" if name else f"  [{cost} SP] — {state}"
                        info.append(("", label, tag))
                        dot_col = self._COLORS["skill_buy"] if active else self._COLORS["skill_lock"]
                        detections.append(("dot", dot_col, bx, by, f"{name or 'skill'} {cost}SP"))
                except Exception:
                    info.append(("", "  Error reading skills", "bad"))
                for btn, thr, label in [("learn_btn", 0.72, "Learn button"), ("confirm_btn", 0.72, "Confirm button")]:
                    pos, conf = self._vision.find_template_conf(btn, ss, thr)
                    if pos:
                        pct = int(conf * 100)
                        info.append(("", f"  {label} : {pct}%", "ok"))
                        detections.append(("dot", self._COLORS["button"], pos[0], pos[1], f"{label} {pct}%"))

            if screen in (GameScreen.RACE, GameScreen.RACE_START, GameScreen.UNKNOWN):
                for btn in self._RACE_BUTTONS:
                    pos, conf = self._vision.find_template_conf(btn, ss, 0.70)
                    if pos and gx <= pos[0] <= gx + gw:
                        short = btn.replace("race_view_results_", "vr_").replace("btn_", "")
                        pct = int(conf * 100)
                        info.append(("", f"  {short} ({pct}%)", "ok"))
                        detections.append(("dot", self._COLORS["button"], pos[0], pos[1], f"{short} {pct}%"))

            if screen == GameScreen.STRATEGY:
                info.append(("STRATEGY", "", "header"))
                for s in self._STRATEGY_TEMPLATES:
                    pos, conf = self._vision.find_template_conf(s, ss, 0.75)
                    if pos:
                        short = s.replace("strategy_", "")
                        pct = int(conf * 100)
                        info.append(("", f"  {short} ({pct}%)", "ok"))
                        detections.append(("dot", self._COLORS["button"], pos[0], pos[1], f"{short} {pct}%"))

            if screen == GameScreen.UNITY:
                info.append(("UNITY", "", "header"))
                for btn in self._UNITY_BUTTONS:
                    pos, conf = self._vision.find_template_conf(btn, ss, 0.70)
                    if pos and gx <= pos[0] <= gx + gw:
                        short = btn.replace("btn_", "")
                        pct = int(conf * 100)
                        info.append(("", f"  {short} ({pct}%)", "ok"))
                        detections.append(("dot", self._COLORS["button"], pos[0], pos[1], f"{short} {pct}%"))

            if screen in (GameScreen.MAIN, GameScreen.RACE_SELECT, GameScreen.RACE,
                          GameScreen.RACE_START, GameScreen.TRAINING):
                gdate = self._vision.read_game_date(ss)
                if gdate:
                    ds = f"{gdate.get('year','')} {gdate.get('half','')} {gdate.get('month','')}".strip()
                    if gdate.get("turn"):
                        ds += f" (turn {gdate['turn']})"
                    info.append(("DATE", ds, None))

            gen_btns = list(self._GENERIC_BUTTONS)
            found_gen = []
            for btn in gen_btns:
                pos, conf = self._vision.find_template_conf(btn, ss, 0.70)
                if pos and gx <= pos[0] <= gx + gw:
                    short = btn.replace("btn_", "")
                    pct = int(conf * 100)
                    found_gen.append(f"{short} ({pct}%)")
                    detections.append(("dot", self._COLORS["button"], pos[0], pos[1], f"{short} {pct}%"))
            if found_gen:
                info.append(("GENERIC", ", ".join(found_gen), None))

            self._last_ss = ss
            self._last_detections = detections
            self._last_info = info
            self._last_game_rect = (gx, gy, gw, gh)
            self.after(0, self._update_ui)

        except Exception as exc:
            err_msg = str(exc)
            self.after(0, lambda: self._show_error(err_msg))
        finally:
            self._busy = False
            self.after(0, lambda: self._refresh_btn.configure(state="normal"))

    def _show_error(self, msg):
        self._status_var.set(f"Error: {msg}")
        self._busy = False
        self._refresh_btn.configure(state="normal")

    def _update_ui(self):
        import cv2
        import numpy as np

        ss = self._last_ss
        detections = self._last_detections
        info = self._last_info

        overlay = ss.copy()
        font = cv2.FONT_HERSHEY_SIMPLEX

        for det in detections:
            col = det[1]
            label = det[-1] if isinstance(det[-1], str) else ""

            if det[0] == "rect":
                _, _, x1, y1, x2, y2, _ = det
                cv2.rectangle(overlay, (x1, y1), (x2, y2), col, 2)
                if label:
                    (tw, th), _ = cv2.getTextSize(label, font, 0.45, 1)
                    lx, ly = x1 + 4, y1 - 6
                    sub = overlay[max(0, ly-th-2):max(0, ly+3), max(0, lx-2):min(overlay.shape[1], lx+tw+2)]
                    if sub.size > 0:
                        overlay[max(0, ly-th-2):max(0, ly+3), max(0, lx-2):min(overlay.shape[1], lx+tw+2)] = (sub * 0.3).astype(np.uint8)
                    cv2.putText(overlay, label, (lx, ly), font, 0.45, col, 1, cv2.LINE_AA)

            elif det[0] == "dot":
                _, _, x, y, _ = det
                cv2.circle(overlay, (x, y), 12, col, 2)
                cv2.circle(overlay, (x, y), 3, col, -1)
                if label:
                    (tw, th), _ = cv2.getTextSize(label, font, 0.45, 1)
                    lx, ly = x + 16, y + 5
                    sub = overlay[max(0, ly-th-2):max(0, ly+3), max(0, lx-2):min(overlay.shape[1], lx+tw+2)]
                    if sub.size > 0:
                        overlay[max(0, ly-th-2):max(0, ly+3), max(0, lx-2):min(overlay.shape[1], lx+tw+2)] = (sub * 0.3).astype(np.uint8)
                    cv2.putText(overlay, label, (lx, ly), font, 0.45, col, 1, cv2.LINE_AA)

        self._overlay_bgr = overlay
        self._redraw_image()

        self._info_text.configure(state="normal")
        self._info_text.delete("1.0", "end")
        for label, value, tag in info:
            line = f"{label}: {value}\n" if label else f"{value}\n"
            self._info_text.insert("end", line, tag or ())
        self._info_text.configure(state="disabled")

        self._status_var.set("Capture complete")

    def _show_event_db_match(self, info, title):
        db_path = Path("config/event_database.json")
        if not db_path.exists():
            return
        db = json.loads(db_path.read_text(encoding="utf-8"))
        search = (title or "").strip().lower()
        if not search:
            return

        all_events = []
        for cn, ce in db.get("character_events", {}).items():
            for en, d in ce.items():
                all_events.append((en, d, f"character ({cn})"))
        for cn, cd in db.get("support_card_events", {}).items():
            for en, d in cd.get("events", {}).items():
                all_events.append((en, d, f"support ({cn})"))
        for en, d in db.get("common_events", {}).items():
            all_events.append((en, d, "common"))

        best_name, best_data, best_src, best_score = None, None, None, 0.0
        for en, d, src in all_events:
            a = en.lower().strip()
            s = 1.0 if a == search else (0.95 if a in search else SequenceMatcher(None, a, search).ratio())
            if s > best_score:
                best_name, best_data, best_src, best_score = en, d, src, s

        if best_name and best_score >= 0.5:
            pct = f"{best_score:.0%}"
            info.append(("", f"  [DB] {best_name} ({best_src}) [{pct}]", "ok"))
            choices_data = best_data.get("choices", {})
            for num in sorted(choices_data, key=lambda x: int(x) if x.isdigit() else 0):
                c = choices_data[num]
                desc = c.get("description", "")
                label = f"Choice {num}" if num != "0" else "Auto"
                desc_part = f" ({desc})" if desc and desc != "auto" else ""
                if "outcomes" in c:
                    info.append(("", f"    {label}{desc_part}:", None))
                    for variant, outcome in c["outcomes"].items():
                        info.append(("", f"      [{variant}] {self._format_outcome(outcome)}", None))
                else:
                    info.append(("", f"    {label}{desc_part}: {self._format_outcome(c)}", None))
        else:
            info.append(("", f"  [DB] No match for \"{title}\"", "warn"))

    @staticmethod
    def _format_outcome(data):
        parts = []
        eff = data.get("effects", {})
        if eff:
            parts.append(", ".join(f"{k}: {v:+d}" for k, v in eff.items()))
        skills = data.get("skills", [])
        if skills:
            sk = [f"{s['name']} +{s['level']}" if isinstance(s, dict) else str(s) for s in skills]
            parts.append("skills: " + ", ".join(sk))
        return " | ".join(parts) or "(no effects)"

    @staticmethod
    def _skill_icon_active(ss, x, y, radius=18):
        import cv2
        import numpy as np
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
            (hsv[:, :, 1] >= 60) & (hsv[:, :, 2] >= 100)
        )
        return float(np.sum(green_mask)) / max(1, roi.shape[0] * roi.shape[1]) >= 0.10

    def _ocr_skill_name(self, ss, icon_x, icon_y, gx, gw, gh, gy):
        import cv2
        import numpy as np
        from scripts.vision.ocr import _ocr_text_raw
        xf = self._vision._aspect_x_factor(gw, gh)
        x1 = gx + int(gw * 0.08 * xf)
        x2 = gx + int(gw * 0.73 * xf)
        search_top = max(gy, icon_y - int(gh * 0.130))
        search_bot = max(gy + 1, icon_y - int(gh * 0.008))
        scan = ss[search_top:search_bot, x1:x2]
        if scan.size == 0:
            return ""
        gray_scan = cv2.cvtColor(scan, cv2.COLOR_BGR2GRAY).astype(float)
        edge_rows = [y for y in range(gray_scan.shape[0])
                     if float(np.abs(np.diff(gray_scan[y])).mean()) > 2.0]
        if not edge_rows:
            return ""
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
        candidates = []
        for min_dist_frac in [0.10, 0.05, 0.02]:
            min_dist = max(3, int(scan_h * min_dist_frac))
            candidates = [c for c in clusters if scan_h - max(c) > min_dist]
            if candidates:
                break
        if not candidates:
            return ""
        title_cluster = candidates[-1]
        t_y1 = max(0, min(title_cluster) - 3)
        t_y2 = min(scan.shape[0], max(title_cluster) + 6)
        roi = scan[t_y1:t_y2]
        if roi.size == 0:
            return ""
        scale = 3
        big = cv2.resize(roi, (roi.shape[1] * scale, roi.shape[0] * scale), interpolation=cv2.INTER_CUBIC)
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
        return self._snap_skill_name(best_raw)

    @staticmethod
    def _snap_skill_name(raw):
        if not raw:
            return ""
        try:
            db_path = os.path.join("config", "skills.json")
            if not os.path.exists(db_path):
                return raw
            with open(db_path, encoding="utf-8") as f:
                skills = json.load(f)
            names = [s["name"] for s in skills]
            raw_words = set(raw.lower().split())
            best_name, best_score = raw, 0.0
            for n in names:
                n_words = set(n.lower().replace("\u25ce", "").replace("\u25cb", "").split())
                if raw_words & n_words:
                    ws = len(raw_words & n_words) / max(1, len(n_words))
                    ss = SequenceMatcher(None, raw.lower(), n.lower()).ratio()
                    score = ws * 0.6 + ss * 0.4
                else:
                    score = SequenceMatcher(None, raw.lower(), n.lower()).ratio()
                if score > best_score:
                    best_score = score
                    best_name = n
            return best_name if best_score >= 0.25 else raw
        except Exception:
            return raw

    def _ocr_skill_cost(self, ss, icon_x, icon_y, gx, gw, gh, gy):
        import cv2
        from scripts.vision.ocr import _ocr_digits
        cost_x1 = max(0, icon_x - int(gw * 0.25))
        cost_x2 = max(0, icon_x - int(gw * 0.01))
        cost_y1 = max(0, icon_y - int(gh * 0.035))
        cost_y2 = min(ss.shape[0], icon_y + int(gh * 0.035))
        if cost_x2 <= cost_x1 or cost_y2 <= cost_y1:
            return "?"
        roi = ss[cost_y1:cost_y2, cost_x1:cost_x2]
        if roi.size == 0:
            return "?"
        scale = 3
        big = cv2.resize(roi, (roi.shape[1] * scale, roi.shape[0] * scale), interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)
        try:
            result = _ocr_digits(thresh).strip()
            return result if result else "?"
        except Exception:
            return "?"

    def _redraw_image(self):
        if not hasattr(self, "_overlay_bgr") or self._overlay_bgr is None:
            return
        import cv2
        from PIL import Image, ImageTk

        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        if cw < 10 or ch < 10:
            return

        h, w = self._overlay_bgr.shape[:2]
        scale = min(cw / w, ch / h)
        nw, nh = int(w * scale), int(h * scale)
        resized = cv2.resize(self._overlay_bgr, (nw, nh), interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb)
        self._photo = ImageTk.PhotoImage(img)
        self._canvas.delete("all")
        self._canvas.create_image(cw // 2, ch // 2, image=self._photo, anchor="center")
