import json
import logging
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from pathlib import Path
import ctypes

def get_resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

if __name__ == "__main__" or __package__ is None:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))
    os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))
    from scripts.gui.config import CONFIG_PATH, DEFAULT_CONFIG
    from scripts.gui.prereqs import _check_easyocr, check_prerequisites, PrerequisiteDialog
else:
    from .config import CONFIG_PATH, DEFAULT_CONFIG
    from .prereqs import _check_easyocr, check_prerequisites, PrerequisiteDialog
    from updater import check_update_async

class _GuiLogHandler(logging.Handler):

    def __init__(self, log_fn):
        super().__init__()
        self.log_fn = log_fn
        self.setFormatter(logging.Formatter("%(name)s - %(levelname)s - %(message)s"))

    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_fn(msg)
        except Exception:
            pass

class BotLauncher(tk.Tk):

    BG        = "#1e1e2e"
    BG_ALT    = "#252538"
    ACCENT    = "#7c6fff"
    ACCENT_HV = "#6a5de0"
    FG        = "#cdd6f4"
    FG_DIM    = "#888ca8"
    GREEN     = "#5a9e57"
    RED       = "#c45c6a"
    YELLOW    = "#b89b4a"
    BORDER    = "#393952"

    def __init__(self):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
        super().__init__()
        self.withdraw()
        my_app_id = 'Bourbot.Mihono.Automation.1.0.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(my_app_id)
        self.title("Mihono Bourbot")
        self.geometry("860x900")
        self.resizable(False, True)
        self.configure(bg=self.BG)
        self._apply_icon()
        self.config_data = self._load_config()
        self.bot_thread = None
        self.bot_running = False
        self.bot_paused = False
        self._active_bot = None
        self._setup_styles()
        self._build_ui()
        self._update_status_bar()
        self.update_idletasks()
        self.deiconify()
        self.after(200, self._check_prerequisites_on_start)
        self.after(4000, lambda: check_update_async(self))
    def _apply_icon(self):
        ico_path = get_resource_path(os.path.join("assets", "logo.ico"))
        if not os.path.exists(ico_path):
            ico_path = os.path.join(os.getcwd(), "assets", "logo.ico")
        if not os.path.exists(ico_path):
            return
        try:
            from PIL import Image, ImageTk
            raw = Image.open(ico_path)
            best = raw.copy().convert("RGBA")
            try:
                for i in range(1, getattr(raw, "n_frames", 1)):
                    raw.seek(i)
                    if raw.size[0] > best.size[0]:
                        best = raw.copy().convert("RGBA")
            except Exception:
                pass
            photo = ImageTk.PhotoImage(best.resize((256, 256), Image.LANCZOS))
            self.iconphoto(True, photo)
            self._icon_img = photo
        except Exception:
            try:
                self.iconbitmap(default=ico_path)
            except Exception:
                pass

    def _setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure(".", background=self.BG, foreground=self.FG,
                         font=("Segoe UI", 10))
        style.configure("TFrame", background=self.BG)
        style.configure("TLabel", background=self.BG, foreground=self.FG,
                         font=("Segoe UI", 10))
        style.configure("Dim.TLabel", foreground=self.FG_DIM, font=("Segoe UI", 9))

        style.configure("TLabelframe", background=self.BG, foreground=self.ACCENT,
                         bordercolor=self.BORDER, relief="groove",
                         font=("Segoe UI Semibold", 10))
        style.configure("TLabelframe.Label", background=self.BG,
                         foreground=self.ACCENT, font=("Segoe UI Semibold", 10))

        style.configure("TNotebook", background=self.BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=self.BG_ALT,
                         foreground=self.FG_DIM, padding=[16, 8],
                         font=("Segoe UI Semibold", 10))
        style.map("TNotebook.Tab",
                  background=[("selected", self.BG), ("active", self.BG_ALT)],
                  foreground=[("selected", self.ACCENT), ("active", self.FG)],
                  padding=[("selected", [16, 8])])

        style.configure("TButton", background=self.ACCENT,
                         foreground="#ffffff", font=("Segoe UI Semibold", 10),
                         padding=[12, 5], borderwidth=0)
        style.map("TButton",
                  background=[("active", self.ACCENT_HV), ("pressed", self.ACCENT_HV)],
                  foreground=[("disabled", self.FG_DIM)])

        style.configure("Accent.TButton", background=self.GREEN,
                         foreground="#ffffff", font=("Segoe UI Bold", 10),
                         padding=[14, 6])
        style.map("Accent.TButton",
                  background=[("active", "#4d8a4b"), ("pressed", "#4d8a4b")])

        style.configure("Danger.TButton", background=self.RED,
                         foreground="#ffffff", font=("Segoe UI Bold", 10),
                         padding=[14, 6])
        style.map("Danger.TButton",
                  background=[("active", "#a84d5a"), ("pressed", "#a84d5a")])

        style.configure("Warning.TButton", background=self.YELLOW,
                         foreground="#ffffff", font=("Segoe UI Bold", 10),
                         padding=[14, 6])
        style.map("Warning.TButton",
                  background=[("active", "#9e853f"), ("pressed", "#9e853f")])

        style.configure("TEntry", fieldbackground=self.BG_ALT,
                         foreground=self.FG, borderwidth=1,
                         insertcolor=self.FG)
        style.configure("TSpinbox", fieldbackground=self.BG_ALT,
                         foreground=self.FG, arrowcolor=self.ACCENT)
        style.configure("TCombobox", fieldbackground=self.BG_ALT,
                         foreground=self.FG, arrowcolor=self.ACCENT,
                         selectbackground=self.ACCENT)
        style.map("TCombobox",
                  fieldbackground=[("readonly", self.BG_ALT)],
                  selectbackground=[("readonly", self.ACCENT)])

        style.configure("TScrollbar", background=self.BG_ALT,
                         troughcolor=self.BG, arrowcolor=self.ACCENT)

        style.configure("Status.TLabel", background=self.BG_ALT,
                         foreground=self.FG_DIM, font=("Segoe UI", 9),
                         padding=[8, 4])

    def _check_prerequisites_on_start(self):
        issues = check_prerequisites()
        has_problems = (
            issues.get("python_version")
            or issues["python_packages"]
            or issues["easyocr"]
            or issues["templates"]
        )
        if has_problems:
            dlg = PrerequisiteDialog(self, issues)
            self.wait_window(dlg)

    def _load_config(self):
        if Path(CONFIG_PATH).exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return DEFAULT_CONFIG.copy()

    def _save_config(self):
        try:
            cfg = self.config_data

            cfg["training_targets"]["speed"] = int(self.speed_var.get())
            cfg["training_targets"]["stamina"] = int(self.stamina_var.get())
            cfg["training_targets"]["power"] = int(self.power_var.get())
            cfg["training_targets"]["wit"] = int(self.wit_var.get())
            cfg["training_targets"]["guts"] = int(self.guts_var.get())
            cfg["training_targets"]["tolerance"] = int(self.tolerance_var.get())

            cfg["stat_priority"] = list(self.priority_listbox.get(0, tk.END))

            cfg["race_strategy"]["default"] = self.strategy_var.get()

            cfg["scenario"] = self.scenario_var.get()

            cfg["thresholds"]["energy_low"] = int(self.energy_low_var.get())
            cfg["thresholds"]["energy_training"] = int(self.energy_train_var.get())
            cfg["thresholds"]["rainbow_energy_min"] = int(
                self.rainbow_energy_var.get()
            )

            cfg["safety_settings"]["emergency_stop_key"] = self.stop_key_var.get()

            cfg["automation_settings"]["action_delay_min"] = float(
                self.delay_min_var.get()
            )
            cfg["automation_settings"]["action_delay_max"] = float(
                self.delay_max_var.get()
            )
            cfg["automation_settings"]["template_match_threshold"] = float(
                self.threshold_var.get()
            )

            if hasattr(self, "skill_interval_var"):
                cfg["skill_check_interval"] = int(self.skill_interval_var.get())
            if hasattr(self, "_skill_wishlist"):
                cfg["skill_wishlist"] = list(self._skill_wishlist)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4)

            self.config_data = cfg
            self._log("Configuration saved.")
        except Exception as e:
            messagebox.showerror("Error", "Failed to save config:\n" + str(e))

    def _build_ui(self):
        try:
            from updater import get_current_version
            _ver = get_current_version()
        except Exception:
            _ver = "?.?.?"
        header = tk.Frame(self, bg=self.BG)
        header.pack(fill="x", padx=16, pady=(12, 4))
        tk.Label(
            header, text="\u265e Mihono Bourbot", font=("Segoe UI Bold", 16),
            bg=self.BG, fg=self.ACCENT,
        ).pack(side="left")
        tk.Label(
            header, text=f"{_ver}", font=("Segoe UI", 10),
            bg=self.BG, fg=self.FG_DIM,
        ).pack(side="left", padx=(8, 0), pady=(5, 0))

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=12, pady=6)

        tab_stats = ttk.Frame(notebook)
        notebook.add(tab_stats, text="  Stats & Priority  ")
        self._build_stats_tab(tab_stats)

        tab_race = ttk.Frame(notebook)
        notebook.add(tab_race, text="  Race & Thresholds  ")
        self._build_race_tab(tab_race)

        tab_skills = ttk.Frame(notebook)
        notebook.add(tab_skills, text="  Skills  ")
        self._build_skills_tab(tab_skills)

        tab_auto = ttk.Frame(notebook)
        notebook.add(tab_auto, text="  Automation & Safety  ")
        self._build_auto_tab(tab_auto)

        tab_log = ttk.Frame(notebook)
        notebook.add(tab_log, text="  Log  ")
        self._build_log_tab(tab_log)

        ctrl = ttk.LabelFrame(self, text="Controls")
        ctrl.pack(fill="x", padx=12, pady=(4, 2))

        left = ttk.Frame(ctrl)
        left.pack(side="left", padx=10, pady=10)

        ttk.Label(left, text="Runs:").pack(side="left", padx=(0, 4))
        self.runs_var = tk.StringVar(value="1")
        ttk.Spinbox(
            left, from_=1, to=100, width=5, textvariable=self.runs_var
        ).pack(side="left", padx=(0, 14))

        ttk.Button(left, text="\U0001f4be  Save Config", command=self._save_config).pack(
            side="left", padx=4
        )

        right = ttk.Frame(ctrl)
        right.pack(side="right", padx=10, pady=10)

        self.start_btn = ttk.Button(
            right, text="\u25b6  Start", command=self._start_bot, width=12,
            style="Accent.TButton",
        )
        self.start_btn.pack(side="left", padx=4)

        self.pause_btn = ttk.Button(
            right, text="\u23f8  Pause", command=self._pause_bot, width=12,
            state="disabled", style="Warning.TButton",
        )
        self.pause_btn.pack(side="left", padx=4)

        self.stop_btn = ttk.Button(
            right, text="\u23f9  Stop", command=self._stop_bot, width=12,
            state="disabled", style="Danger.TButton",
        )
        self.stop_btn.pack(side="left", padx=4)

        self.status_var = tk.StringVar(value="Ready")
        self.status_bar = ttk.Label(
            self, textvariable=self.status_var, style="Status.TLabel",
            relief="flat", anchor="w",
        )
        self.status_bar.pack(fill="x", padx=12, pady=(2, 10))

    def _build_stats_tab(self, parent):
        cfg = self.config_data
        targets = cfg["training_targets"]

        grp = ttk.LabelFrame(parent, text="Stat Targets")
        grp.pack(fill="x", padx=10, pady=8)

        stats_info = [
            ("Speed", targets.get("speed", 600)),
            ("Stamina", targets.get("stamina", 600)),
            ("Power", targets.get("power", 600)),
            ("Wit", targets.get("wit", 600)),
            ("Guts", targets.get("guts", 600)),
        ]

        self.speed_var = tk.StringVar(value=str(stats_info[0][1]))
        self.stamina_var = tk.StringVar(value=str(stats_info[1][1]))
        self.power_var = tk.StringVar(value=str(stats_info[2][1]))
        self.wit_var = tk.StringVar(value=str(stats_info[3][1]))
        self.guts_var = tk.StringVar(value=str(stats_info[4][1]))

        vars_list = [
            self.speed_var, self.stamina_var, self.power_var,
            self.wit_var, self.guts_var,
        ]

        for i, (label, _) in enumerate(stats_info):
            ttk.Label(grp, text=label + ":").grid(
                row=i, column=0, padx=8, pady=4, sticky="w"
            )
            ttk.Entry(grp, textvariable=vars_list[i], width=10).grid(
                row=i, column=1, padx=8, pady=4
            )
            sc = tk.Scale(
                grp, from_=0, to=1200, orient="horizontal", length=300,
                variable=vars_list[i],
                bg=self.BG, fg=self.FG, troughcolor=self.BG_ALT,
                highlightthickness=0, sliderrelief="flat",
                activebackground=self.ACCENT,
            )
            sc.grid(row=i, column=2, padx=8, pady=4)

        self.tolerance_var = tk.StringVar(value=str(targets.get("tolerance", 50)))
        ttk.Label(grp, text="Tolerance:").grid(
            row=5, column=0, padx=8, pady=4, sticky="w"
        )
        ttk.Entry(grp, textvariable=self.tolerance_var, width=10).grid(
            row=5, column=1, padx=8, pady=4
        )
        ttk.Label(
            grp, text="(stop training a stat when within this many points)",
            style="Dim.TLabel",
        ).grid(row=5, column=2, padx=8, pady=4, sticky="w")

        pgrp = ttk.LabelFrame(parent, text="Stat Priority (drag to reorder)")
        pgrp.pack(fill="x", padx=10, pady=8)

        self.priority_listbox = tk.Listbox(
            pgrp, height=5, width=20, font=("Consolas", 11),
            bg=self.BG_ALT, fg=self.FG, selectbackground=self.ACCENT,
            selectforeground="#ffffff", highlightthickness=1,
            highlightcolor=self.ACCENT, highlightbackground=self.BORDER,
            relief="flat", bd=0,
        )
        self.priority_listbox.pack(side="left", padx=10, pady=8)
        for s in cfg.get("stat_priority", ["speed", "power", "stamina", "wit", "guts"]):
            self.priority_listbox.insert(tk.END, s)

        btn_col = ttk.Frame(pgrp)
        btn_col.pack(side="left", padx=8)
        ttk.Button(btn_col, text="\u25b2 Up", command=self._priority_up).pack(pady=4)
        ttk.Button(btn_col, text="\u25bc Down", command=self._priority_down).pack(pady=4)

        ttk.Label(pgrp, text=(
            "The bot trains the first stat in this list\n"
            "that hasn't reached its target yet."
        )).pack(side="left", padx=16)

        pre_grp = ttk.LabelFrame(parent, text="Quick Presets")
        pre_grp.pack(fill="x", padx=10, pady=8)

        presets = {
            "Sprint": {
                "speed": 1200, "stamina": 400, "power": 800, "wit": 1000, "guts": 400,
                "priority": ["speed", "wit", "power", "stamina", "guts"],
            },
            "Mile": {
                "speed": 1200, "stamina": 600, "power": 800, "wit": 800, "guts": 400,
                "priority": ["speed", "power", "wit", "stamina", "guts"],
            },
            "Medium": {
                "speed": 1200, "stamina": 800, "power": 700, "wit": 600, "guts": 400,
                "priority": ["speed", "stamina", "power", "wit", "guts"],
            },
            "Long": {
                "speed": 1200, "stamina": 1000, "power": 700, "wit": 400, "guts": 400,
                "priority": ["speed", "stamina", "power", "guts", "wit"],
            },
        }

        for name, preset in presets.items():
            ttk.Button(
                pre_grp, text=name,
                command=lambda p=preset: self._apply_preset(p),
            ).pack(side="left", padx=8, pady=6)

    def _build_race_tab(self, parent):
        cfg = self.config_data
        strat = cfg.get("race_strategy", {})
        thresh = cfg.get("thresholds", {})

        sgrp = ttk.LabelFrame(parent, text="Scenario")
        sgrp.pack(fill="x", padx=10, pady=8)

        self.scenario_var = tk.StringVar(
            value=cfg.get("scenario", "unity_cup")
        )

        ttk.Label(sgrp, text="Scenario:").grid(
            row=0, column=0, padx=8, pady=6, sticky="w"
        )
        ttk.Combobox(
            sgrp, textvariable=self.scenario_var,
            values=["unity_cup", "ura"], width=14, state="readonly",
        ).grid(row=0, column=1, padx=8)
        ttk.Label(
            sgrp,
            text="Unity Cup = URA + spirit bursts & unity matches. URA = base scenario only.",
            style="Dim.TLabel",
        ).grid(row=0, column=2, padx=8, sticky="w")

        grp = ttk.LabelFrame(parent, text="Race Strategy")
        grp.pack(fill="x", padx=10, pady=8)

        options = ["Front", "Pace", "Late", "End"]

        self.strategy_var = tk.StringVar(value=strat.get("default", "End"))

        ttk.Label(grp, text="Strategy:").grid(row=0, column=0, padx=8, pady=6, sticky="w")
        ttk.Combobox(
            grp, textvariable=self.strategy_var, values=options, width=14, state="readonly"
        ).grid(row=0, column=1, padx=8)
        ttk.Label(
            grp, text="The bot will select this running strategy before each race.",
            style="Dim.TLabel",
        ).grid(row=0, column=2, padx=8, sticky="w")

        tgrp = ttk.LabelFrame(parent, text="Action Thresholds")
        tgrp.pack(fill="x", padx=10, pady=8)

        self.energy_low_var = tk.StringVar(value=str(thresh.get("energy_low", 40)))
        self.energy_train_var = tk.StringVar(
            value=str(thresh.get("energy_training", 50))
        )
        self.rainbow_energy_var = tk.StringVar(
            value=str(thresh.get("rainbow_energy_min", 40))
        )

        labels = [
            ("Rest if energy below (%):", self.energy_low_var),
            ("Allow training if energy above (%):", self.energy_train_var),
            ("Rainbow training min energy (%):", self.rainbow_energy_var),
        ]
        for i, (label, var) in enumerate(labels):
            ttk.Label(tgrp, text=label).grid(
                row=i, column=0, padx=8, pady=6, sticky="w"
            )
            ttk.Spinbox(tgrp, from_=0, to=100, width=6, textvariable=var).grid(
                row=i, column=1, padx=8
            )

        info = ttk.LabelFrame(parent, text="Decision Priority (read-only)")
        info.pack(fill="x", padx=10, pady=8)
        priorities = [
            "1. Mandatory Races (Target / Scheduled)",
            "2. Debuff Management (Infirmary)",
            "3. Rainbow Training (2+ supports, if energy > threshold)",
            "4. Low Energy (Rest)",
            "5. Bad Mood (Recreation)",
            "6. Training (friendship first, then stat priority)",
        ]
        for p in priorities:
            ttk.Label(info, text=p).pack(anchor="w", padx=12, pady=2)

    def _build_skills_tab(self, parent):
        import json as _json
        cfg = self.config_data
        SKILLS_JSON = os.path.join("config", "skills.json")
        all_skills = []
        try:
            with open(SKILLS_JSON, encoding="utf-8") as f:
                all_skills = [s["name"] for s in _json.load(f)]
        except Exception:
            pass

        top = ttk.LabelFrame(parent, text="Skill Buying")
        top.pack(fill="x", padx=12, pady=(10, 6))
        ttk.Label(
            top,
            text=(
                "The bot will attempt to buy skills from this wishlist every N training turns.\n"
                "Skills are matched by fuzzy name — minor OCR differences are tolerated."
            ),
            style="Dim.TLabel",
        ).pack(anchor="w", padx=10, pady=(6, 2))
        interval_row = ttk.Frame(top)
        interval_row.pack(anchor="w", padx=10, pady=(2, 8))
        ttk.Label(interval_row, text="Check every N turns:").pack(side="left")
        self.skill_interval_var = tk.StringVar(
            value=str(cfg.get("skill_check_interval", 8))
        )
        ttk.Spinbox(
            interval_row, from_=1, to=50, width=6,
            textvariable=self.skill_interval_var,
        ).pack(side="left", padx=(6, 0))

        body = tk.Frame(parent, bg=self.BG)
        body.pack(fill="both", expand=True, padx=12, pady=4)

        left_frame = tk.Frame(body, bg=self.BG)
        left_frame.pack(side="left", fill="both", expand=True)

        mid_frame = tk.Frame(body, bg=self.BG, width=110)
        mid_frame.pack(side="left", fill="y", padx=8)
        mid_frame.pack_propagate(False)

        right_frame = tk.Frame(body, bg=self.BG)
        right_frame.pack(side="left", fill="both", expand=True)

        tk.Label(
            left_frame,
            text=f"Available Skills ({len(all_skills)})",
            font=("Segoe UI Semibold", 10),
            bg=self.BG, fg=self.ACCENT,
        ).pack(anchor="w", pady=(0, 2))

        search_var = tk.StringVar()
        ttk.Entry(left_frame, textvariable=search_var).pack(fill="x")
        ttk.Label(left_frame, text="Search:", style="Dim.TLabel").pack(anchor="w")

        avail_frame = tk.Frame(left_frame, bg=self.BG)
        avail_frame.pack(fill="both", expand=True)
        avail_listbox = tk.Listbox(
            avail_frame, selectmode="extended", bg=self.BG_ALT,
            fg=self.FG, selectbackground=self.ACCENT, selectforeground="#ffffff",
            borderwidth=0, highlightthickness=1, highlightbackground=self.BORDER,
            font=("Segoe UI", 10), activestyle="none",
        )
        avail_scroll = ttk.Scrollbar(avail_frame, command=avail_listbox.yview)
        avail_listbox.configure(yscrollcommand=avail_scroll.set)
        avail_scroll.pack(side="right", fill="y")
        avail_listbox.pack(side="left", fill="both", expand=True)

        btn_inner = tk.Frame(mid_frame, bg=self.BG)
        btn_inner.place(relx=0.5, rely=0.5, anchor="center")
        ttk.Button(btn_inner, text="Add →", width=10,
                   command=lambda: _add_skills()).pack(pady=4)
        ttk.Button(btn_inner, text="← Remove", width=10,
                   command=lambda: _remove_skills()).pack(pady=4)
        ttk.Button(btn_inner, text="Clear All", width=10,
                   command=lambda: (
                       self._skill_wishlist.clear(),
                       _refresh_wish(),
                       _update_cfg(),
                   )).pack(pady=4)

        tk.Label(
            right_frame, text="Wishlist",
            font=("Segoe UI Semibold", 10),
            bg=self.BG, fg=self.ACCENT,
        ).pack(anchor="w", pady=(0, 2))

        wish_frame = tk.Frame(right_frame, bg=self.BG)
        wish_frame.pack(fill="both", expand=True)
        wish_listbox = tk.Listbox(
            wish_frame, selectmode="extended", bg=self.BG_ALT,
            fg=self.FG, selectbackground=self.ACCENT, selectforeground="#ffffff",
            borderwidth=0, highlightthickness=1, highlightbackground=self.BORDER,
            font=("Segoe UI", 10), activestyle="none",
        )
        wish_scroll = ttk.Scrollbar(wish_frame, command=wish_listbox.yview)
        wish_listbox.configure(yscrollcommand=wish_scroll.set)
        wish_scroll.pack(side="right", fill="y")
        wish_listbox.pack(side="left", fill="both", expand=True)

        tk.Label(
            parent,
            text="Double-click to remove  |  Double-click available list to add",
            font=("Segoe UI", 8), bg=self.BG_ALT, fg=self.FG_DIM, anchor="w",
        ).pack(fill="x", padx=12, pady=(2, 4))

        self._skill_wishlist = list(cfg.get("skill_wishlist", []))
        self._all_skills = all_skills

        def _filtered():
            q = search_var.get().lower()
            return [s for s in self._all_skills if q in s.lower()] if q else self._all_skills

        def _refresh_avail():
            avail_listbox.delete(0, tk.END)
            for s in _filtered():
                avail_listbox.insert(tk.END, s)

        def _refresh_wish():
            wish_listbox.delete(0, tk.END)
            for s in self._skill_wishlist:
                wish_listbox.insert(tk.END, s)

        def _update_cfg():
            self.config_data["skill_wishlist"] = list(self._skill_wishlist)

        def _add_skills():
            for i in avail_listbox.curselection():
                name = avail_listbox.get(i)
                if name not in self._skill_wishlist:
                    self._skill_wishlist.append(name)
            _refresh_wish()
            _update_cfg()

        def _remove_skills():
            for i in reversed(wish_listbox.curselection()):
                del self._skill_wishlist[i]
            _refresh_wish()
            _update_cfg()

        search_var.trace_add("write", lambda *_: _refresh_avail())
        avail_listbox.bind("<Double-Button-1>", lambda e: _add_skills())
        wish_listbox.bind("<Double-Button-1>", lambda e: _remove_skills())
        _refresh_avail()
        _refresh_wish()

    def _build_auto_tab(self, parent):
        cfg = self.config_data
        auto = cfg.get("automation_settings", {})
        safety = cfg.get("safety_settings", {})

        grp = ttk.LabelFrame(parent, text="Automation Settings")
        grp.pack(fill="x", padx=10, pady=8)

        self.delay_min_var = tk.StringVar(
            value=str(auto.get("action_delay_min", 1.0))
        )
        self.delay_max_var = tk.StringVar(
            value=str(auto.get("action_delay_max", 3.0))
        )
        self.threshold_var = tk.StringVar(
            value=str(auto.get("template_match_threshold", 0.8))
        )

        rows = [
            ("Min action delay (s):", self.delay_min_var),
            ("Max action delay (s):", self.delay_max_var),
            ("Template match threshold (0-1):", self.threshold_var),
        ]
        for i, (label, var) in enumerate(rows):
            ttk.Label(grp, text=label).grid(
                row=i, column=0, padx=8, pady=6, sticky="w"
            )
            ttk.Entry(grp, textvariable=var, width=10).grid(row=i, column=1, padx=8)

        sgrp = ttk.LabelFrame(parent, text="Safety Settings")
        sgrp.pack(fill="x", padx=10, pady=8)

        self.stop_key_var = tk.StringVar(
            value=safety.get("emergency_stop_key", "F12")
        )

        ttk.Label(sgrp, text="Emergency stop key:").grid(
            row=0, column=0, padx=8, pady=6, sticky="w"
        )
        ttk.Combobox(
            sgrp, textvariable=self.stop_key_var,
            values=["F12", "F11", "F10", "end", "pause"], width=10,
            state="readonly",
        ).grid(row=0, column=1, padx=8)

        tgrp = ttk.LabelFrame(parent, text="Tools")
        tgrp.pack(fill="x", padx=10, pady=8)

        ttk.Button(
            tgrp, text="Check Prerequisites", command=self._recheck_prereqs
        ).pack(side="left", padx=8, pady=8)

        ttk.Button(
            tgrp, text="Vision Test", command=self._test_vision
        ).pack(side="left", padx=8, pady=8)

        info = ttk.LabelFrame(parent, text="How it works")
        info.pack(fill="x", padx=10, pady=8)
        ttk.Label(
            info,
            text=(
                "This bot interacts with the game window via win32 messages.\n"
                "It does NOT take over your mouse or keyboard.\n"
                "You can continue using your PC while the bot runs.\n\n"
                "The bot captures screenshots of the game window only,\n"
                "uses template matching + OCR to read the game state,\n"
                "and sends click events directly to the game window."
            ),
            justify="left",
        ).pack(padx=12, pady=8)

    def _build_log_tab(self, parent):
        self.log_text = scrolledtext.ScrolledText(
            parent, state="disabled", wrap="word", font=("Consolas", 9),
            bg=self.BG_ALT, fg=self.FG, insertbackground=self.FG,
            selectbackground=self.ACCENT, selectforeground="#ffffff",
            highlightthickness=0, relief="flat", bd=0,
        )
        self.log_text.pack(fill="both", expand=True, padx=8, pady=8)
        ttk.Button(parent, text="Clear Log", command=self._clear_log).pack(
            pady=(0, 8)
        )

    def _priority_up(self):
        sel = self.priority_listbox.curselection()
        if not sel or sel[0] == 0:
            return
        idx = sel[0]
        val = self.priority_listbox.get(idx)
        self.priority_listbox.delete(idx)
        self.priority_listbox.insert(idx - 1, val)
        self.priority_listbox.selection_set(idx - 1)

    def _priority_down(self):
        sel = self.priority_listbox.curselection()
        if not sel or sel[0] >= self.priority_listbox.size() - 1:
            return
        idx = sel[0]
        val = self.priority_listbox.get(idx)
        self.priority_listbox.delete(idx)
        self.priority_listbox.insert(idx + 1, val)
        self.priority_listbox.selection_set(idx + 1)

    def _apply_preset(self, preset):
        self.speed_var.set(str(preset["speed"]))
        self.stamina_var.set(str(preset["stamina"]))
        self.power_var.set(str(preset["power"]))
        self.wit_var.set(str(preset["wit"]))
        self.guts_var.set(str(preset["guts"]))
        self.priority_listbox.delete(0, tk.END)
        for s in preset["priority"]:
            self.priority_listbox.insert(tk.END, s)
        self._log("Preset applied.")

    def _log(self, message):
        def _write():
            self.log_text.configure(state="normal")
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state="disabled")
        try:
            self.after(0, _write)
        except Exception:
            pass

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state="disabled")

    def _update_status_bar(self):
        if self.bot_running and self.bot_paused:
            self.status_var.set("Status: PAUSED")
        elif self.bot_running:
            self.status_var.set("Status: RUNNING...")
        else:
            ocr = "OK" if _check_easyocr() else "MISSING"
            self.status_var.set("Status: Ready  |  EasyOCR: " + ocr)
        self.after(2000, self._update_status_bar)

    def _start_bot(self):
        if self.bot_running:
            messagebox.showwarning("Warning", "Bot is already running!")
            return

        self._save_config()

        num_runs = int(self.runs_var.get())
        self.bot_running = True
        self.bot_paused = False
        self.start_btn.configure(state="disabled")
        self.pause_btn.configure(state="normal")
        self.stop_btn.configure(state="normal")

        self._log("Starting bot for " + str(num_runs) + " run(s)...")

        gui_log_handler = _GuiLogHandler(self._log)

        def _run():
            try:
                from scripts import MihonoBourbot

                bot = MihonoBourbot(config_path=CONFIG_PATH)
                logging.getLogger().addHandler(gui_log_handler)
                self._active_bot = bot
                bot.run(num_runs=num_runs)
            except Exception as e:
                self._log("ERROR: " + str(e))
            finally:
                logging.getLogger().removeHandler(gui_log_handler)
                self.bot_running = False
                self.bot_paused = False
                self._active_bot = None
                self.after(0, self._reset_buttons)
                self._log("Bot has stopped.")

        self.bot_thread = threading.Thread(target=_run, daemon=True)
        self.bot_thread.start()

    def _pause_bot(self):
        if not self.bot_running:
            return

        if self.bot_paused:
            self.bot_paused = False
            if self._active_bot:
                self._active_bot.resume()
            self.pause_btn.configure(text="\u23f8  Pause")
            self._log("Bot RESUMED.")
        else:
            self.bot_paused = True
            if self._active_bot:
                self._active_bot.pause()
            self.pause_btn.configure(text="\u25b6  Resume")
            self._log("Bot PAUSED.")

    def _stop_bot(self):
        if self._active_bot:
            self._active_bot.emergency_stop()
            self._log("Stop signal sent.")
        self.bot_running = False
        self.bot_paused = False
        self._reset_buttons()

    def _reset_buttons(self):
        self.start_btn.configure(state="normal")
        self.pause_btn.configure(state="disabled", text="\u23f8  Pause")
        self.stop_btn.configure(state="disabled")

    def _recheck_prereqs(self):
        issues = check_prerequisites()
        has_problems = (
            issues.get("python_version")
            or issues["python_packages"]
            or issues["easyocr"]
            or issues["templates"]
        )
        if has_problems:
            dlg = PrerequisiteDialog(self, issues)
            self.wait_window(dlg)
        else:
            messagebox.showinfo("All Good", "All prerequisites are met!")

    def _test_vision(self):
        self._save_config()
        self._log("Starting vision test...")

        def _run():
            try:
                from scripts import MihonoBourbot

                bot = MihonoBourbot(config_path=CONFIG_PATH)
                bot.test_vision()
            except Exception as e:
                self._log("ERROR: " + str(e))

        threading.Thread(target=_run, daemon=True).start()

def main():
    Path("logs").mkdir(exist_ok=True)
    Path("templates").mkdir(exist_ok=True)
    Path("config").mkdir(exist_ok=True)

    app = BotLauncher()
    app.mainloop()

if __name__ == "__main__":
    main()