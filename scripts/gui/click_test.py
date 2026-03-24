import json
import random
import time
import threading
import tkinter as tk
from tkinter import ttk

class ClickTestDialog(tk.Toplevel):

    BG      = "#1e1e2e"
    BG_ALT  = "#252538"
    BG_CARD = "#2a2a3e"
    ACCENT  = "#7c6fff"
    FG      = "#cdd6f4"
    FG_DIM  = "#888ca8"
    GREEN   = "#5a9e57"
    RED     = "#c45c6a"
    ORANGE  = "#b89b4a"
    BORDER  = "#393952"

    _COL_WAIT    = "#555577"
    _COL_RUNNING = "#7c6fff"
    _COL_OK      = "#5a9e57"
    _COL_FAIL    = "#c45c6a"
    _COL_SKIP    = "#444455"

    _PLATFORM_LABELS = {
        "google_play": "Google Play",
        "ldplayer":    "LDPlayer",
        "steam":       "Steam",
    }

    _METHODS_BY_PLATFORM = {
        "google_play": [
            ("gp_1_post_no_hover",
             "Standard click",
             "The classic way — the bot clicks directly on the button.",
             False),
            ("gp_2_post_hover",
             "Click with cursor hover",
             "The bot moves the cursor to the button first, then clicks.",
             False),
            ("gp_3_send_hover",
             "Precise click",
             "A more deliberate click — the bot waits for each action to complete.",
             False),
            ("gp_4_mixed_hover",
             "Combined click",
             "Mixes the hover and precise techniques together.",
             False),
            ("gp_5_triple_hover",
             "Insistent hover click",
             "The bot moves to the button three times before clicking.",
             False),
            ("gp_6_fg_hover",
             "Focus + click",
             "Brings the emulator window to the front, then clicks.",
             False),
        ],
        "ldplayer": [
            ("ld_1_child_no_hover",
             "Standard click",
             "The classic way — clicks directly in the game area.",
             False),
            ("ld_2_child_post_hover",
             "Click with cursor hover",
             "Moves the cursor to the button first, then clicks in the game area.",
             False),
            ("ld_3_child_send_hover",
             "Precise click",
             "A deliberate click in the game area — waits for each action to complete.",
             False),
            ("ld_4_parent_post_hover",
             "Window-level hover click",
             "Clicks at the emulator window level instead of the game area.",
             False),
            ("ld_5_parent_send_hover",
             "Window-level precise click",
             "Precise click at the emulator window level.",
             False),
            ("ld_6_child_triple_hover",
             "Insistent hover click",
             "Moves to the button three times, then clicks in the game area.",
             False),
        ],
        "steam": [
            ("st_1_cursor_activate_send",
             "Standard click  ⚠ moves mouse",
             "The classic way — moves the mouse to the button and clicks.\nYour mouse cursor will move during this test.",
             True),
            ("st_2_fg_cursor_send",
             "Focus + cursor click  ⚠ moves mouse",
             "Brings the game to the front first, then moves the mouse and clicks.\nYour mouse cursor will move during this test.",
             True),
            ("st_3_cursor_msg_hover",
             "Cursor + hover click  ⚠ moves mouse",
             "Moves the mouse and also sends a hover signal before clicking.\nYour mouse cursor will move during this test.",
             True),
            ("st_4_no_cursor_send",
             "Background click  (mouse stays)",
             "Tries to click without moving your mouse at all.",
             False),
            ("st_5_cursor_post",
             "Fast cursor click  ⚠ moves mouse",
             "Moves the mouse then uses a faster click variant.\nYour mouse cursor will move during this test.",
             True),
            ("st_6_mouse_event",
             "Direct system click  ⚠ moves mouse",
             "Uses the most direct system-level click available.\nYour mouse cursor will move during this test.",
             True),
        ],
    }

    _STEPS = [
        "Opened the Training screen",
        "Browsed all training options",
        "Returned to the home screen",
        "Opened the Skills screen",
        "Scrolled through the skills list",
        "Returned to the home screen",
    ]

    _STEP_KEYS = [
        "training_btn",
        "training_stats",
        "back_training",
        "skills_btn",
        "skills_scroll",
        "back_skills",
    ]

    _STAT_ORDER = [
        ("stamina", 0.322, 0.843),
        ("power",   0.500, 0.843),
        ("guts",    0.678, 0.843),
        ("wit",     0.855, 0.843),
        ("speed",   0.145, 0.843),
    ]

    def __init__(self, parent, config_path):
        super().__init__(parent)
        self.title("Click Test")
        self.configure(bg=self.BG)
        self.minsize(860, 560)

        with open(config_path, encoding="utf-8") as f:
            self._config = json.load(f)
        self._config_path = config_path

        self._platform = self._config.get("platform", "google_play")
        self._methods  = self._METHODS_BY_PLATFORM[self._platform]
        self._current_idx = 0
        self._results     = {}
        self._running     = False
        self._stop_flag   = False

        self._step_states  = ["wait"] * len(self._STEPS)
        self._step_frames  = []
        self._step_dots    = []
        self._step_labels  = []
        self._test_dots    = []

        self._build_ui()
        self._refresh_test_list()
        self._show_test(0)

    def _build_ui(self):
        top = tk.Frame(self, bg=self.BG)
        top.pack(fill="x", padx=14, pady=(12, 0))

        tk.Label(
            top, text="Click Test",
            bg=self.BG, fg=self.FG, font=("Segoe UI", 13, "bold"),
        ).pack(side="left")

        tk.Label(
            top,
            text="  —  We'll test a few ways of clicking to find the one that works best for you.",
            bg=self.BG, fg=self.FG_DIM, font=("Segoe UI", 9),
        ).pack(side="left")

        pf_frame = tk.Frame(self, bg=self.BG)
        pf_frame.pack(fill="x", padx=14, pady=(6, 0))

        tk.Label(
            pf_frame, text="Your emulator / platform:",
            bg=self.BG, fg=self.FG_DIM, font=("Segoe UI", 9),
        ).pack(side="left")

        self._platform_var = tk.StringVar(value=self._platform)
        plat_cb = ttk.Combobox(
            pf_frame, textvariable=self._platform_var,
            values=list(self._PLATFORM_LABELS.keys()),
            width=16, state="readonly",
        )
        plat_cb.pack(side="left", padx=(6, 0))
        plat_cb.bind("<<ComboboxSelected>>", self._on_platform_changed)

        self._plat_label = tk.Label(
            pf_frame,
            text=f"  ({self._PLATFORM_LABELS[self._platform]})",
            bg=self.BG, fg=self.ACCENT, font=("Segoe UI", 9, "italic"),
        )
        self._plat_label.pack(side="left")

        tk.Frame(self, bg=self.BORDER, height=1).pack(fill="x", padx=14, pady=(10, 0))

        body = tk.PanedWindow(
            self, orient="horizontal", bg=self.BORDER,
            sashwidth=4, sashrelief="flat",
        )
        body.pack(fill="both", expand=True, padx=8, pady=8)

        left = tk.Frame(body, bg=self.BG, width=180)
        body.add(left, stretch="never")

        tk.Label(
            left, text="Tests",
            bg=self.BG, fg=self.FG_DIM, font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", padx=8, pady=(6, 4))

        self._tests_container = tk.Frame(left, bg=self.BG)
        self._tests_container.pack(fill="both", expand=True, padx=4)

        right = tk.Frame(body, bg=self.BG)
        body.add(right, stretch="always")

        self._card = tk.Frame(right, bg=self.BG_CARD, padx=16, pady=12)
        self._card.pack(fill="x", padx=6, pady=(6, 0))

        self._test_counter = tk.Label(
            self._card, text="", bg=self.BG_CARD, fg=self.FG_DIM,
            font=("Segoe UI", 9),
        )
        self._test_counter.pack(anchor="w")

        self._test_name_lbl = tk.Label(
            self._card, text="", bg=self.BG_CARD, fg=self.FG,
            font=("Segoe UI", 12, "bold"), anchor="w",
        )
        self._test_name_lbl.pack(anchor="w", pady=(2, 0))

        self._test_desc_lbl = tk.Label(
            self._card, text="", bg=self.BG_CARD, fg=self.FG_DIM,
            font=("Segoe UI", 9), anchor="w", justify="left",
        )
        self._test_desc_lbl.pack(anchor="w", pady=(4, 0))

        self._mouse_warn_lbl = tk.Label(
            self._card, text="",
            bg="#3a1e1e", fg="#ffaaaa",
            font=("Segoe UI", 9), anchor="w", padx=8, pady=4,
        )

        steps_outer = tk.Frame(right, bg=self.BG)
        steps_outer.pack(fill="both", expand=True, padx=6, pady=(10, 4))

        tk.Label(
            steps_outer,
            text="What happened during this test:",
            bg=self.BG, fg=self.FG_DIM, font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        hint = tk.Label(
            steps_outer,
            text="After the test finishes, tap any row to correct it if the bot got it wrong.",
            bg=self.BG, fg=self.FG_DIM, font=("Segoe UI", 8, "italic"),
        )
        hint.pack(anchor="w", pady=(0, 8))
        self._hint_lbl = hint

        self._steps_frame = tk.Frame(steps_outer, bg=self.BG)
        self._steps_frame.pack(fill="x")

        for i, label in enumerate(self._STEPS):
            row = tk.Frame(self._steps_frame, bg=self.BG, cursor="arrow")
            row.pack(fill="x", pady=3)

            dot_canvas = tk.Canvas(
                row, width=20, height=20,
                bg=self.BG, highlightthickness=0,
            )
            dot_canvas.pack(side="left", padx=(0, 10))
            dot_canvas.create_oval(2, 2, 18, 18, fill=self._COL_WAIT, outline="", tags="dot")

            lbl = tk.Label(
                row, text=label,
                bg=self.BG, fg=self.FG_DIM,
                font=("Segoe UI", 10), anchor="w",
            )
            lbl.pack(side="left", fill="x", expand=True)

            self._step_frames.append(row)
            self._step_dots.append(dot_canvas)
            self._step_labels.append(lbl)

        btn_bar = tk.Frame(self, bg=self.BG)
        btn_bar.pack(fill="x", padx=14, pady=(0, 10))

        self._start_btn = tk.Button(
            btn_bar, text="\u25b6  Start test",
            font=("Segoe UI", 10, "bold"),
            bg=self.ACCENT, fg="white", activebackground="#6a5de0",
            relief="flat", padx=16, pady=6,
            command=self._on_start,
        )
        self._start_btn.pack(side="left", padx=(0, 8))

        self._skip_btn = tk.Button(
            btn_bar, text="Skip this test",
            font=("Segoe UI", 9),
            bg=self.BG_ALT, fg=self.FG_DIM, activebackground=self.BORDER,
            relief="flat", padx=12, pady=6,
            command=self._on_skip,
        )
        self._skip_btn.pack(side="left", padx=(0, 8))

        self._next_btn = tk.Button(
            btn_bar, text="Next test  \u2192",
            font=("Segoe UI", 9),
            bg=self.BG_ALT, fg=self.FG_DIM, activebackground=self.BORDER,
            relief="flat", padx=12, pady=6,
            command=self._on_next,
            state="disabled",
        )
        self._next_btn.pack(side="left", padx=(0, 8))

        self._report_btn = tk.Button(
            btn_bar, text="\U0001f4cb  Get report",
            font=("Segoe UI", 9),
            bg=self.BG_ALT, fg=self.FG_DIM, activebackground=self.BORDER,
            relief="flat", padx=12, pady=6,
            command=self._on_report,
            state="disabled",
        )
        self._report_btn.pack(side="left")

        self._stop_btn = tk.Button(
            btn_bar, text="\u25a0  Stop",
            font=("Segoe UI", 9),
            bg="#3a1e1e", fg="#ffaaaa", activebackground="#4a2020",
            relief="flat", padx=12, pady=6,
            command=self._on_stop,
            state="disabled",
        )
        self._stop_btn.pack(side="right")

        self._status_var = tk.StringVar(value="Ready — press \"Start test\" to begin.")
        tk.Label(
            self, textvariable=self._status_var,
            bg=self.BG, fg=self.FG_DIM, font=("Segoe UI", 9), anchor="w",
        ).pack(fill="x", padx=14, pady=(0, 6))

    def _refresh_test_list(self):
        for w in self._tests_container.winfo_children():
            w.destroy()
        self._test_dots.clear()

        for i, (mid, name, desc, moves) in enumerate(self._methods):
            row = tk.Frame(self._tests_container, bg=self.BG)
            row.pack(fill="x", pady=2)

            dot = tk.Canvas(row, width=14, height=14, bg=self.BG, highlightthickness=0)
            dot.pack(side="left", padx=(0, 6))
            dot.create_oval(1, 1, 13, 13, fill=self._COL_WAIT, outline="", tags="dot")
            self._test_dots.append(dot)

            lbl = tk.Label(
                row, text=f"Test {i + 1}",
                bg=self.BG, fg=self.FG_DIM, font=("Segoe UI", 9),
            )
            lbl.pack(side="left")

    def _set_test_dot(self, idx, color):
        if 0 <= idx < len(self._test_dots):
            self._test_dots[idx].itemconfigure("dot", fill=color)

    def _show_test(self, idx):
        mid, name, desc, moves = self._methods[idx]
        n = len(self._methods)
        self._test_counter.configure(text=f"Test {idx + 1} of {n}")
        self._test_name_lbl.configure(text=name)
        self._test_desc_lbl.configure(text=desc)

        if moves:
            self._mouse_warn_lbl.configure(
                text="\u26a0  Your mouse cursor will move during this test."
                     " Make sure the game window is fully visible."
            )
            self._mouse_warn_lbl.pack(fill="x", pady=(8, 0))
        else:
            self._mouse_warn_lbl.pack_forget()

        for i in range(len(self._STEPS)):
            self._set_step("wait", i)
        self._set_steps_clickable(False)
        self._hint_lbl.configure(fg=self.FG_DIM)

        self._set_test_dot(idx, self.ACCENT)
        self._status_var.set(f"Test {idx + 1} of {n} ready — press \"Start test\".")

    def _set_step(self, state, idx):
        self._step_states[idx] = state
        colors = {
            "wait":    (self._COL_WAIT,    self.FG_DIM),
            "running": (self._COL_RUNNING, self.FG),
            "ok":      (self._COL_OK,      self.FG),
            "fail":    (self._COL_FAIL,    self.FG),
            "skip":    (self._COL_SKIP,    self.FG_DIM),
        }
        dot_col, fg_col = colors.get(state, (self._COL_WAIT, self.FG_DIM))
        self._step_dots[idx].itemconfigure("dot", fill=dot_col)
        self._step_labels[idx].configure(fg=fg_col)

    def _set_steps_clickable(self, enabled):
        for i, row in enumerate(self._step_frames):
            idx = i

            def make_toggle(n):
                def _toggle(e):
                    if not self._running:
                        cur = self._step_states[n]
                        new = "fail" if cur == "ok" else "ok"
                        self._set_step(new, n)
                return _toggle

            if enabled:
                row.configure(cursor="hand2")
                for w in (row, self._step_dots[idx], self._step_labels[idx]):
                    w.bind("<Button-1>", make_toggle(idx))
            else:
                row.configure(cursor="arrow")
                for w in (row, self._step_dots[idx], self._step_labels[idx]):
                    try:
                        w.unbind("<Button-1>")
                    except Exception:
                        pass

    def _update_step_ui(self, state, idx):
        try:
            self.after(0, lambda: self._set_step(state, idx))
        except Exception:
            pass

    def _set_status(self, msg):
        try:
            self.after(0, lambda: self._status_var.set(msg))
        except Exception:
            pass

    def _on_platform_changed(self, _=None):
        if self._running:
            return
        new_pf = self._platform_var.get()
        if new_pf == self._platform:
            return
        self._platform = new_pf
        self._methods  = self._METHODS_BY_PLATFORM[self._platform]
        self._current_idx = 0
        self._results = {}
        self._plat_label.configure(text=f"  ({self._PLATFORM_LABELS[self._platform]})")
        self._refresh_test_list()
        self._show_test(0)
        self._next_btn.configure(state="disabled")
        self._report_btn.configure(state="disabled")
        self._set_status("Platform changed — all results reset.")

    def _on_start(self):
        if self._running:
            return
        self._running   = True
        self._stop_flag = False
        self._start_btn.configure(state="disabled")
        self._skip_btn.configure(state="disabled")
        self._next_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        self._set_steps_clickable(False)
        for i in range(len(self._STEPS)):
            self._set_step("wait", i)
        mid, name, _, _ = self._methods[self._current_idx]
        self._set_test_dot(self._current_idx, self.ACCENT)
        self._set_status(f"Test {self._current_idx + 1} running…  Please don't touch the keyboard or mouse.")
        threading.Thread(target=self._run_sequence, args=(mid,), daemon=True).start()

    def _on_stop(self):
        self._stop_flag = True
        self._set_status("Stopping…")

    def _on_skip(self):
        if self._running:
            return
        mid, name, _, _ = self._methods[self._current_idx]
        self._results[mid] = {"name": name, "skipped": True, "steps": {}}
        self._set_test_dot(self._current_idx, self._COL_SKIP)
        self._advance()

    def _on_next(self):
        mid, name, _, _ = self._methods[self._current_idx]
        steps = {self._STEP_KEYS[i]: (self._step_states[i] == "ok")
                 for i in range(len(self._STEPS))}
        passed = sum(steps.values())
        n = len(self._STEPS)
        self._results[mid] = {"name": name, "skipped": False, "steps": steps}
        dot_col = self._COL_OK if passed == n else (self.ORANGE if passed > 0 else self._COL_FAIL)
        self._set_test_dot(self._current_idx, dot_col)
        self._advance()

    def _advance(self):
        self._current_idx += 1
        if self._current_idx >= len(self._methods):
            self._start_btn.configure(state="disabled")
            self._skip_btn.configure(state="disabled")
            self._next_btn.configure(state="disabled")
            self._report_btn.configure(state="normal")
            self._set_status("All done!  Press \"Get report\" to see the results.")
        else:
            self._show_test(self._current_idx)
            self._next_btn.configure(state="disabled")

    def _run_sequence(self, method_id):
        try:
            from scripts.vision import VisionModule
            from scripts.models import GameScreen
            from scripts.automation.clicks import click_test_dispatch, scroll_test_dispatch

            vision = VisionModule(self._config)
            vision.find_game_window()

            if not vision.game_hwnd:
                self._set_status("Game window not found — check the Window tab.")
                self._finish_run()
                return

            hwnd = vision.game_hwnd
            ox   = vision._client_offset_x
            oy   = vision._client_offset_y

            def click(sx, sy):
                cx = int(sx) - ox + random.randint(-4, 4)
                cy = int(sy) - oy + random.randint(-4, 4)
                click_test_dispatch(method_id, hwnd, cx, cy)

            def stopped():
                return self._stop_flag

            self._update_step_ui("running", 0)
            self._set_status("Clicking on Training…")
            ss = vision.take_screenshot()
            pos = vision.find_template("btn_training", ss, 0.72)
            if pos:
                gx, gy, gw, gh = vision.get_game_rect(ss)
                tx, ty = pos
                ty += int(gh * -0.045)
                click(tx, ty)
                time.sleep(2.5)
                s2 = vision.detect_screen(vision.take_screenshot())
                ok = (s2 == GameScreen.TRAINING)
                self._update_step_ui("ok" if ok else "fail", 0)
            else:
                self._update_step_ui("fail", 0)

            if stopped():
                self._finish_run()
                return

            self._update_step_ui("running", 1)
            self._set_status("Clicking on training options…")
            ss = vision.take_screenshot()
            gx, gy, gw, gh = vision.get_game_rect(ss)
            xf  = vision._aspect_x_factor(gw, gh)
            cal = vision._calibration
            stat_ok = True
            for stat, def_x, def_y in self._STAT_ORDER:
                if stopped():
                    stat_ok = False
                    break
                tp = cal.get(f"train_{stat}", {})
                px = gx + int(gw * tp.get("x", def_x) * xf)
                py = gy + int(gh * tp.get("y", def_y))
                click(px, py)
                time.sleep(0.8)
            self._update_step_ui("ok" if stat_ok else "fail", 1)

            if stopped():
                self._finish_run()
                return

            self._update_step_ui("running", 2)
            self._set_status("Going back to the home screen…")
            time.sleep(0.3)
            ss  = vision.take_screenshot()
            pos = vision.find_template("btn_back", ss, 0.72)
            if pos:
                click(*pos)
            else:
                ss2  = vision.take_screenshot()
                gx2, gy2, gw2, gh2 = vision.get_game_rect(ss2)
                xf2  = vision._aspect_x_factor(gw2, gh2)
                click(gx2 + int(gw2 * 0.06 * xf2), gy2 + int(gh2 * 0.02))
            time.sleep(2.5)
            s2 = vision.detect_screen(vision.take_screenshot())
            self._update_step_ui("ok" if s2 == GameScreen.MAIN else "fail", 2)

            if stopped():
                self._finish_run()
                return

            self._update_step_ui("running", 3)
            self._set_status("Opening the Skills screen…")
            ss  = vision.take_screenshot()
            pos = vision.find_template("btn_skills", ss, 0.72)
            if pos:
                gx3, gy3, gw3, gh3 = vision.get_game_rect(ss)
                sx, sy = pos
                sy += int(gh3 * -0.030)
                click(sx, sy)
                time.sleep(2.5)
                s2 = vision.detect_screen(vision.take_screenshot())
                self._update_step_ui("ok" if s2 == GameScreen.SKILL_SELECT else "fail", 3)
            else:
                self._update_step_ui("fail", 3)

            if stopped():
                self._finish_run()
                return

            self._update_step_ui("running", 4)
            self._set_status("Scrolling through the skills list…")
            scroll_ok = True
            for n in range(5):
                if stopped():
                    scroll_ok = False
                    break
                ss = vision.take_screenshot()
                gx4, gy4, gw4, gh4 = vision.get_game_rect(ss)
                scx = (gx4 + gw4 // 2) - ox
                sfy = (gy4 + int(gh4 * 0.65)) - oy
                sto = (gy4 + int(gh4 * 0.45)) - oy
                scroll_test_dispatch(method_id, hwnd, scx, sfy, sto)
                time.sleep(0.8)
            self._update_step_ui("ok" if scroll_ok else "fail", 4)

            if stopped():
                self._finish_run()
                return

            self._update_step_ui("running", 5)
            self._set_status("Going back to the home screen…")
            time.sleep(0.3)
            ss  = vision.take_screenshot()
            pos = vision.find_template("btn_back", ss, 0.72)
            if pos:
                click(*pos)
            else:
                self._update_step_ui("fail", 5)
                self._finish_run()
                return
            time.sleep(2.5)
            s2 = vision.detect_screen(vision.take_screenshot())
            self._update_step_ui("ok" if s2 == GameScreen.MAIN else "fail", 5)

            self._finish_run()

        except Exception as e:
            self._set_status(f"Error: {e}")
            for i in range(len(self._STEPS)):
                if self._step_states[i] == "running":
                    self._update_step_ui("fail", i)
            self._finish_run()

    def _finish_run(self):
        self._running = False
        ok_count = sum(1 for s in self._step_states if s == "ok")
        n = len(self._STEPS)

        def _ui():
            self._start_btn.configure(state="normal")
            self._skip_btn.configure(state="normal")
            self._stop_btn.configure(state="disabled")
            self._next_btn.configure(state="normal")
            self._set_steps_clickable(True)
            self._hint_lbl.configure(fg=self.FG)
            if ok_count == n:
                self._status_var.set("Everything worked! \u2713  Tap Next to continue, or Get report if this is good enough.")
            elif ok_count > 0:
                self._status_var.set(f"{ok_count} of {n} steps worked.  Tap a step to correct it, then press Next.")
            else:
                self._status_var.set("Nothing worked with this attempt.  Press Next to try the next one.")

        try:
            self.after(0, _ui)
        except Exception:
            pass

    def _on_report(self):
        import platform as _plat
        lines = []
        lines.append("=" * 62)
        lines.append("  MIHONO BOURBOT — CLICK TEST REPORT")
        lines.append("=" * 62)
        lines.append("")
        lines.append(f"OS           : {_plat.platform()}")
        try:
            import ctypes as _ct
            dpi = _ct.windll.user32.GetDpiForSystem()
        except Exception:
            dpi = "unknown"
        lines.append(f"System DPI   : {dpi}")
        lines.append(f"Platform     : {self._platform}")
        lines.append(f"Window       : {self._config.get('window_title', '(auto)')}")
        lines.append("")
        n_steps = len(self._STEPS)
        best_name, best_score, perfect = None, -1, []
        for mid, data in self._results.items():
            name = data["name"]
            if data.get("skipped"):
                lines.append(f"[SKIP]  {name}")
                lines.append("  Skipped by user.")
                lines.append("")
                continue
            steps  = data["steps"]
            passed = sum(1 for v in steps.values() if v)
            all_ok = passed == n_steps
            lines.append(f"[{'OK  ' if all_ok else f'{passed}/{n_steps} '}]  {name}")
            lines.append(f"  Method ID : {mid}")
            for key, ok in steps.items():
                lbl = self._STEPS[self._STEP_KEYS.index(key)] if key in self._STEP_KEYS else key
                lines.append(f"  {'[OK]' if ok else '[--]'}  {lbl}")
            lines.append("")
            if all_ok:
                perfect.append((name, mid))
            if passed > best_score:
                best_score, best_name = passed, name
        lines.append("=" * 62)
        lines.append("RECOMMENDATION")
        lines.append("")
        if perfect:
            lines.append("Method(s) where everything worked:")
            for n, mid in perfect:
                lines.append(f"  OK  {n}  (id: {mid})")
        elif best_name:
            lines.append(f"Best partial result: {best_name} ({best_score}/{n_steps} steps)")
        else:
            lines.append("No methods fully tested.")
        lines.append("")
        lines.append("=" * 62)
        lines.append("Please share this report with the developer.")
        report = "\n".join(lines)

        dlg = tk.Toplevel(self)
        dlg.title("Click Test Report")
        dlg.configure(bg=self.BG)
        dlg.geometry("700x520")

        tk.Label(
            dlg, text="Results",
            bg=self.BG, fg=self.FG, font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w", padx=14, pady=(12, 4))

        tk.Label(
            dlg,
            text="Copy this and send it to the developer so they can set up the best click method for you.",
            bg=self.BG, fg=self.FG_DIM, font=("Segoe UI", 9),
        ).pack(anchor="w", padx=14, pady=(0, 8))

        txt_frame = tk.Frame(dlg, bg=self.BG)
        txt_frame.pack(fill="both", expand=True, padx=14, pady=(0, 8))

        txt = tk.Text(
            txt_frame, font=("Consolas", 9), wrap="word",
            bg=self.BG_ALT, fg=self.FG,
            highlightthickness=0, relief="flat", bd=0,
        )
        sb = ttk.Scrollbar(txt_frame, command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        txt.pack(fill="both", expand=True)
        txt.insert(tk.END, report)
        txt.configure(state="disabled")

        btn_row = tk.Frame(dlg, bg=self.BG)
        btn_row.pack(fill="x", padx=14, pady=(0, 12))

        tk.Button(
            btn_row,
            text="\U0001f4cb  Copy to clipboard",
            font=("Segoe UI", 10, "bold"),
            bg=self.ACCENT, fg="white", activebackground="#6a5de0",
            relief="flat", padx=14, pady=6,
            command=lambda: (dlg.clipboard_clear(), dlg.clipboard_append(report)),
        ).pack(side="left")

        tk.Button(
            btn_row, text="Close",
            font=("Segoe UI", 9),
            bg=self.BG_ALT, fg=self.FG_DIM, activebackground=self.BORDER,
            relief="flat", padx=12, pady=6,
            command=dlg.destroy,
        ).pack(side="right")
