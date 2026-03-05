import json
import logging
import os
import sys
import threading
import traceback
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
        self.configure(bg=self.BG)
        self._apply_icon()
        self._splash = self._show_splash()
        self.config_data = self._load_config()
        self.bot_thread = None
        self.bot_running = False
        self.bot_paused = False
        self._active_bot = None
        self.after(10, self._deferred_init)

    def _deferred_init(self):
        self._setup_styles()
        self._build_ui()
        self._update_status_bar()
        self.update_idletasks()
        if self._splash:
            self._splash.destroy()
            self._splash = None
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        win_w = min(900, int(sw * 0.65))
        win_h = min(960, int(sh * 0.85))
        x = (sw - win_w) // 2
        y = (sh - win_h) // 2
        self.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.minsize(760, 640)
        self.resizable(True, True)
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

    def _show_splash(self):
        splash = tk.Toplevel(self)
        splash.overrideredirect(True)
        splash.configure(bg=self.BG)
        w, h = 340, 140
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        splash.geometry(f"{w}x{h}+{x}+{y}")
        splash.attributes("-topmost", True)
        tk.Label(
            splash, text="\u265e Mihono Bourbot",
            font=("Segoe UI Bold", 18), bg=self.BG, fg=self.ACCENT,
        ).pack(pady=(30, 8))
        tk.Label(
            splash, text="Loading\u2026",
            font=("Segoe UI", 11), bg=self.BG, fg=self.FG_DIM,
        ).pack()
        splash.update()
        return splash

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

        style.configure("TCheckbutton", background=self.BG, foreground=self.FG,
                         indicatorcolor=self.BG_ALT,
                         indicatorrelief="flat")
        style.map("TCheckbutton",
                  background=[("active", self.BG)],
                  indicatorcolor=[
                      ("selected", self.ACCENT),
                      ("!selected", self.BG_ALT),
                  ])

        style.configure("Status.TLabel", background=self.BG_ALT,
                         foreground=self.FG_DIM, font=("Segoe UI", 9),
                         padding=[8, 4])

    def _check_prerequisites_on_start(self):
        def _bg():
            result = check_prerequisites()
            self.after(0, lambda: self._show_prereq_issues(result))
        threading.Thread(target=_bg, daemon=True).start()

    def _show_prereq_issues(self, issues):
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
        def _deep_merge(base, override):
            merged = base.copy()
            for k, v in override.items():
                if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
                    merged[k] = _deep_merge(merged[k], v)
                else:
                    merged[k] = v
            return merged

        if Path(CONFIG_PATH).exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            return _deep_merge(DEFAULT_CONFIG, saved)
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
            cfg["race_strategy"]["force_race_insufficient_fans"] = self.force_fans_var.get()

            cfg["scenario"] = self.scenario_var.get()

            cfg["platform"] = self._platform_var.get()

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

        self.status_var = tk.StringVar(value="Ready")
        self.status_bar = ttk.Label(
            self, textvariable=self.status_var, style="Status.TLabel",
            relief="flat", anchor="w",
        )
        self.status_bar.pack(side="bottom", fill="x", padx=12, pady=(2, 10))

        ctrl = ttk.LabelFrame(self, text="Controls")
        ctrl.pack(side="bottom", fill="x", padx=12, pady=(4, 2))

        left = ttk.Frame(ctrl)
        left.pack(side="left", padx=10, pady=10)

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

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=12, pady=6)

        tab_stats = ttk.Frame(notebook)
        notebook.add(tab_stats, text="  Stats & Priority  ")
        self._build_stats_tab(self._scrollable_tab(tab_stats))

        tab_race = ttk.Frame(notebook)
        notebook.add(tab_race, text="  Race & Thresholds  ")
        self._build_race_tab(self._scrollable_tab(tab_race))

        tab_skills = ttk.Frame(notebook)
        notebook.add(tab_skills, text="  Skills  ")
        self._build_skills_tab(tab_skills)

        tab_window = ttk.Frame(notebook)
        notebook.add(tab_window, text="  Window  ")
        self.after_idle(lambda p=self._scrollable_tab(tab_window): self._build_window_tab(p))

        tab_auto = ttk.Frame(notebook)
        notebook.add(tab_auto, text="  Automation & Safety  ")
        self._build_auto_tab(self._scrollable_tab(tab_auto))

        tab_log = ttk.Frame(notebook)
        notebook.add(tab_log, text="  Log  ")
        self._build_log_tab(tab_log)

    def _scrollable_tab(self, tab_frame):
        canvas = tk.Canvas(tab_frame, bg=self.BG, highlightthickness=0, bd=0)
        vsb = ttk.Scrollbar(tab_frame, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        wid = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _update_scroll(e=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            content_h = inner.winfo_reqheight()
            visible_h = canvas.winfo_height()
            if content_h > visible_h:
                if not vsb.winfo_ismapped():
                    vsb.pack(side="right", fill="y")
            else:
                if vsb.winfo_ismapped():
                    vsb.pack_forget()

        inner.bind("<Configure>", _update_scroll)
        canvas.bind("<Configure>", lambda e: (
            canvas.itemconfigure(wid, width=e.width),
            _update_scroll(),
        ))
        canvas.pack(side="left", fill="both", expand=True)
        canvas.configure(yscrollcommand=vsb.set)
        def _on_enter(e):
            canvas.bind_all(
                "<MouseWheel>",
                lambda ev: canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units"),
            )
        def _on_leave(e):
            canvas.unbind_all("<MouseWheel>")
        canvas.bind("<Enter>", _on_enter)
        canvas.bind("<Leave>", _on_leave)
        return inner

    def _build_window_tab(self, parent):
        plat_frame = ttk.LabelFrame(parent, text="Platform / Emulator")
        plat_frame.pack(fill="x", padx=10, pady=8)
        ttk.Label(
            plat_frame,
            text="Select the platform where the game is running.",
            style="Dim.TLabel",
        ).pack(anchor="w", padx=10, pady=(6, 4))

        plat_row = ttk.Frame(plat_frame)
        plat_row.pack(fill="x", padx=10, pady=(0, 8))
        ttk.Label(plat_row, text="Platform:").pack(side="left", padx=(0, 6))
        self._platform_var = tk.StringVar(
            value=self.config_data.get("platform", "google_play")
        )
        plat_combo = ttk.Combobox(
            plat_row, textvariable=self._platform_var,
            values=["google_play", "ldplayer", "steam"], width=16, state="readonly",
        )
        plat_combo.pack(side="left")
        ttk.Label(
            plat_row,
            text="Google Play / LDPlayer = centered.  Steam = wider layout + sidebar.",
            style="Dim.TLabel",
        ).pack(side="left", padx=(12, 0))

        top = ttk.LabelFrame(parent, text="Game Window Selection")
        top.pack(fill="x", padx=10, pady=8)
        ttk.Label(
            top,
            text=(
                "Select the window where the game is running.\n"
                "This allows any emulator or player to be used."
            ),
            style="Dim.TLabel",
        ).pack(anchor="w", padx=10, pady=(6, 4))

        list_frame = tk.Frame(top, bg=self.BG)
        list_frame.pack(fill="x", padx=10, pady=4)

        self._window_listbox = tk.Listbox(
            list_frame, height=8, font=("Segoe UI", 10),
            bg=self.BG_ALT, fg=self.FG, selectbackground=self.ACCENT,
            selectforeground="#ffffff", highlightthickness=1,
            highlightbackground=self.BORDER, relief="flat", bd=0,
        )
        w_scroll = ttk.Scrollbar(list_frame, command=self._window_listbox.yview)
        self._window_listbox.configure(yscrollcommand=w_scroll.set)
        w_scroll.pack(side="right", fill="y")
        self._window_listbox.pack(side="left", fill="both", expand=True)

        btn_row = ttk.Frame(top)
        btn_row.pack(fill="x", padx=10, pady=4)
        ttk.Button(
            btn_row, text="\u21bb  Refresh", command=self._refresh_window_list,
        ).pack(side="left", padx=4)
        ttk.Button(
            btn_row, text="\u2714  Use This Window", command=self._select_game_window,
        ).pack(side="left", padx=4)
        ttk.Button(
            btn_row, text="\u2716  Clear Selection", command=self._clear_window_selection,
        ).pack(side="left", padx=4)

        current_title = self.config_data.get("window_title", "")
        self._selected_window_var = tk.StringVar(
            value=f"Current: {current_title}" if current_title else "No window selected (auto-detect)"
        )
        ttk.Label(top, textvariable=self._selected_window_var).pack(
            anchor="w", padx=10, pady=4,
        )

        preview_frame = ttk.LabelFrame(parent, text="Preview & Info")
        preview_frame.pack(fill="both", expand=True, padx=10, pady=8)

        self._preview_label = tk.Label(
            preview_frame, bg=self.BG_ALT,
            text="Select a window above to see a preview",
            fg=self.FG_DIM, font=("Segoe UI", 10),
        )
        self._preview_label.pack(fill="both", expand=True, padx=10, pady=10)

        self._resolution_var = tk.StringVar(value="")
        ttk.Label(preview_frame, textvariable=self._resolution_var).pack(
            anchor="w", padx=10, pady=(0, 8),
        )

        self._window_list_data = []
        self._preview_image = None
        self._window_listbox.bind("<<ListboxSelect>>", self._on_window_select)
        self.after(300, self._refresh_window_list)

    def _refresh_window_list(self):
        from scripts.vision.capture import CaptureMixin
        self._window_listbox.delete(0, tk.END)
        self._window_list_data = CaptureMixin.enumerate_visible_windows(
            exclude_pid=os.getpid(),
        )
        for _hwnd, title in self._window_list_data:
            self._window_listbox.insert(tk.END, title)

    def _on_window_select(self, event=None):
        sel = self._window_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        hwnd, title = self._window_list_data[idx]
        self._show_window_preview(hwnd, title)

    def _show_window_preview(self, hwnd, title):
        try:
            import win32gui as _wg
            import win32ui as _wu
            import ctypes as _ct
            import numpy as _np

            rect = _wg.GetWindowRect(hwnd)
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]
            if w <= 0 or h <= 0:
                self._preview_label.configure(image="", text="Window has no size")
                return

            client_rect = _wg.GetClientRect(hwnd)
            cw, ch = client_rect[2], client_rect[3]
            client_origin = _wg.ClientToScreen(hwnd, (0, 0))
            off_x = client_origin[0] - rect[0]
            off_y = client_origin[1] - rect[1]

            hwnd_dc = _wg.GetWindowDC(hwnd)
            mfc_dc = _wu.CreateDCFromHandle(hwnd_dc)
            save_dc = mfc_dc.CreateCompatibleDC()
            bitmap = _wu.CreateBitmap()
            bitmap.CreateCompatibleBitmap(mfc_dc, w, h)
            save_dc.SelectObject(bitmap)

            _ct.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 0x00000002)

            bmp_info = bitmap.GetInfo()
            bmp_data = bitmap.GetBitmapBits(True)
            img = _np.frombuffer(bmp_data, dtype=_np.uint8)
            img = img.reshape((bmp_info["bmHeight"], bmp_info["bmWidth"], 4))

            _wg.DeleteObject(bitmap.GetHandle())
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            _wg.ReleaseDC(hwnd, hwnd_dc)

            if off_x > 0 or off_y > 0:
                img = img[off_y:off_y + ch, off_x:off_x + cw]
            else:
                cw, ch = img.shape[1], img.shape[0]

            from PIL import Image, ImageTk
            pil_img = Image.frombuffer(
                "RGBA", (img.shape[1], img.shape[0]),
                img.tobytes(), "raw", "BGRA", 0, 1,
            )
            pil_img.thumbnail((400, 350), Image.LANCZOS)
            photo = ImageTk.PhotoImage(pil_img)

            self._preview_label.configure(image=photo, text="")
            self._preview_image = photo
            self._resolution_var.set(f"Client area: {cw} \u00d7 {ch} px")
        except Exception as e:
            self._preview_label.configure(image="", text=f"Preview failed: {e}")
            self._resolution_var.set("")

    def _select_game_window(self):
        sel = self._window_listbox.curselection()
        if not sel:
            messagebox.showwarning("Warning", "Please select a window first.")
            return
        idx = sel[0]
        _hwnd, title = self._window_list_data[idx]
        self.config_data["window_title"] = title
        self._selected_window_var.set(f"Current: {title}")
        self._log(f"Window selected: {title}")

    def _clear_window_selection(self):
        self.config_data["window_title"] = ""
        self._selected_window_var.set("No window selected (auto-detect)")
        self._log("Window selection cleared — will use auto-detect.")

    def _build_stats_tab(self, parent):
        cfg = self.config_data
        targets = cfg["training_targets"]

        grp = ttk.LabelFrame(parent, text="Stat Targets")
        grp.pack(fill="x", padx=10, pady=8)

        stats_info = [
            ("Speed", targets.get("speed", 600)),
            ("Stamina", targets.get("stamina", 600)),
            ("Power", targets.get("power", 600)),
            ("Guts", targets.get("guts", 600)),
            ("Wit", targets.get("wit", 600)),
        ]

        self.speed_var = tk.StringVar(value=str(stats_info[0][1]))
        self.stamina_var = tk.StringVar(value=str(stats_info[1][1]))
        self.power_var = tk.StringVar(value=str(stats_info[2][1]))
        self.guts_var = tk.StringVar(value=str(stats_info[3][1]))
        self.wit_var = tk.StringVar(value=str(stats_info[4][1]))

        vars_list = [
            self.speed_var, self.stamina_var, self.power_var,
            self.guts_var, self.wit_var,
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

        fan_grp = ttk.LabelFrame(parent, text="Fan Warning")
        fan_grp.pack(fill="x", padx=10, pady=8)
        self.force_fans_var = tk.BooleanVar(
            value=cfg.get("race_strategy", {}).get(
                "force_race_insufficient_fans", True,
            )
        )
        toggle_row = ttk.Frame(fan_grp)
        toggle_row.pack(anchor="w", padx=12, pady=6)
        self._fans_toggle = tk.Canvas(
            toggle_row, width=44, height=24,
            bg=self.BG, highlightthickness=0, bd=0,
        )
        self._fans_toggle.pack(side="left", padx=(0, 10))
        ttk.Label(
            toggle_row,
            text='Force race when "Insufficient Fans" warning appears',
        ).pack(side="left")
        self._draw_toggle(self._fans_toggle, self.force_fans_var.get())
        self._fans_toggle.bind("<Button-1>", lambda e: self._flip_toggle(
            self.force_fans_var, self._fans_toggle,
        ))
        ttk.Label(
            fan_grp,
            text="When enabled, automatically enters the race. When disabled, dismisses the popup.",
            style="Dim.TLabel",
        ).pack(anchor="w", padx=12, pady=(0, 6))

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

    def _draw_toggle(self, canvas, on):
        canvas.delete("all")
        w, h = 44, 24
        r = h // 2
        bg = self.ACCENT if on else self.BG_ALT
        canvas.create_oval(0, 0, h, h, fill=bg, outline=bg)
        canvas.create_oval(w - h, 0, w, h, fill=bg, outline=bg)
        canvas.create_rectangle(r, 0, w - r, h, fill=bg, outline=bg)
        knob_x = w - r - 2 if on else r + 2
        canvas.create_oval(
            knob_x - r + 3, 3, knob_x + r - 3, h - 3,
            fill="#ffffff", outline="#ffffff",
        )

    def _flip_toggle(self, var, canvas):
        var.set(not var.get())
        self._draw_toggle(canvas, var.get())

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

        self.bot_running = True
        self.bot_paused = False
        self.start_btn.configure(state="disabled")
        self.pause_btn.configure(state="normal")
        self.stop_btn.configure(state="normal")

        self._log("Starting bot...")

        gui_log_handler = _GuiLogHandler(self._log)

        def _run():
            try:
                from scripts.gui.prereqs import bootstrap_libs, preload_cv2
                bootstrap_libs()
                preload_cv2()
                from scripts.bot import MihonoBourbot

                bot = MihonoBourbot(config_path=CONFIG_PATH)
                logging.getLogger().addHandler(gui_log_handler)
                self._active_bot = bot
                bot.run(num_runs=1)
            except Exception as e:
                full_tb = traceback.format_exc()
                self._log("ERROR: " + str(e))
                self._log("--- TRACEBACK ---")
                for line in full_tb.splitlines():
                    self._log(line)
                self._log("--- END TRACEBACK ---")
                try:
                    log_dir = Path(os.getcwd()) / "logs"
                    log_dir.mkdir(exist_ok=True)
                    (log_dir / "last_error.log").write_text(full_tb, encoding="utf-8")
                except Exception:
                    pass
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
        self._log("Opening Vision Test...")
        try:
            from scripts.gui.prereqs import bootstrap_libs, preload_cv2
            bootstrap_libs()
            preload_cv2()
            VisionTestDialog(self, CONFIG_PATH)
        except Exception as e:
            full_tb = traceback.format_exc()
            self._log("ERROR: " + str(e))
            for line in full_tb.splitlines():
                self._log(line)


class VisionTestDialog(tk.Toplevel):

    _COLORS = {
        "game_rect":  (0, 255, 0),
        "button":     (128, 255, 128),
        "stat":       (0, 180, 255),
        "energy":     (0, 200, 255),
        "mood":       (255, 128, 0),
        "event":      (200, 100, 255),
        "warning":    (0, 0, 255),
    }

    _MAIN_BUTTONS = [
        "btn_training", "btn_rest", "btn_recreation", "btn_races",
        "btn_rest_summer", "btn_skills",
    ]
    _GENERIC_BUTTONS = [
        "btn_confirm", "btn_ok", "btn_close", "btn_cancel",
        "btn_skip", "btn_tap", "btn_next", "btn_back",
        "btn_race_start", "btn_race_next_finish",
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

            screen = self._vision.detect_screen(ss)
            info.append(("SCREEN", f"{screen.value.upper()}", "header"))

            platform = self._config.get("platform", "google_play")
            info.append(("", f"Platform: {platform}", None))
            info.append(("", f"Game area: {gw}x{gh} at ({gx},{gy})", None))

            detections.append(("rect", self._COLORS["game_rect"], gx, gy, gx + gw, gy + gh, "Game"))

            from scripts.models import GameScreen

            if screen in (GameScreen.MAIN, GameScreen.TRAINING, GameScreen.EVENT,
                          GameScreen.RACE_SELECT, GameScreen.INSUFFICIENT_FANS,
                          GameScreen.SCHEDULED_RACE_POPUP, GameScreen.UNKNOWN):
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
                        info.append(("", f"  {short} — Précision : {pct}%", "ok"))
                        detections.append(("dot", self._COLORS["button"], pos[0], pos[1], f"{short} {pct}%"))

            if screen == GameScreen.TRAINING:
                info.append(("TRAINING", "", "header"))
                rainbow_count = self._vision.detect_rainbow_training(ss)
                bursts = self._vision.detect_burst_training(ss)
                info.append(("", f"  Rainbow: {rainbow_count}", "ok" if rainbow_count else None))
                info.append(("", f"  White bursts: {len(bursts['white'])}", None))
                info.append(("", f"  Blue bursts: {len(bursts['blue'])}", None))

            if screen == GameScreen.EVENT:
                event_type = self._vision.detect_event_type(ss)
                info.append(("EVENT", f"Type: {event_type or 'unknown'}", "header"))

            if screen in (GameScreen.RACE, GameScreen.RACE_START, GameScreen.UNKNOWN):
                for btn in self._RACE_BUTTONS:
                    pos, conf = self._vision.find_template_conf(btn, ss, 0.70)
                    if pos and gx <= pos[0] <= gx + gw:
                        short = btn.replace("race_view_results_", "vr_").replace("btn_", "")
                        pct = int(conf * 100)
                        info.append(("", f"  {short} — Précision : {pct}%", "ok"))
                        detections.append(("dot", self._COLORS["button"], pos[0], pos[1], f"{short} {pct}%"))

            if screen == GameScreen.STRATEGY:
                info.append(("STRATEGY", "", "header"))
                for s in self._STRATEGY_TEMPLATES:
                    pos, conf = self._vision.find_template_conf(s, ss, 0.75)
                    if pos:
                        short = s.replace("strategy_", "")
                        pct = int(conf * 100)
                        info.append(("", f"  {short} — Précision : {pct}%", "ok"))
                        detections.append(("dot", self._COLORS["button"], pos[0], pos[1], f"{short} {pct}%"))

            if screen in (GameScreen.INSUFFICIENT_FANS, GameScreen.SCHEDULED_RACE_POPUP):
                banner = self._vision.identify_popup_banner(ss)
                info.append(("BANNER", banner or "?", "header"))

            if screen in (GameScreen.MAIN, GameScreen.RACE_SELECT, GameScreen.RACE, GameScreen.RACE_START):
                gdate = self._vision.read_game_date(ss)
                if gdate:
                    ds = f"{gdate.get('year','')} {gdate.get('half','')} {gdate.get('month','')}".strip()
                    if gdate.get("turn"):
                        ds += f" (turn {gdate['turn']})"
                    info.append(("DATE", ds, None))

            gen_btns = self._GENERIC_BUTTONS
            if screen in (GameScreen.RACE_SELECT, GameScreen.RACE, GameScreen.RACE_START, GameScreen.TRY_AGAIN):
                gen_btns = [b for b in gen_btns if b != "btn_confirm"]
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
            if det[0] == "rect":
                _, col, x1, y1, x2, y2, label = det
                cv2.rectangle(overlay, (x1, y1), (x2, y2), col, 2)
                if label:
                    (tw, th), _ = cv2.getTextSize(label, font, 0.45, 1)
                    lx, ly = x1 + 4, y1 - 6
                    sub = overlay[max(0, ly - th - 2):max(0, ly + 3), max(0, lx - 2):min(overlay.shape[1], lx + tw + 2)]
                    if sub.size > 0:
                        overlay[max(0, ly - th - 2):max(0, ly + 3), max(0, lx - 2):min(overlay.shape[1], lx + tw + 2)] = (sub * 0.3).astype(np.uint8)
                    cv2.putText(overlay, label, (lx, ly), font, 0.45, col, 1, cv2.LINE_AA)
            elif det[0] == "dot":
                _, col, x, y, label = det
                cv2.circle(overlay, (x, y), 12, col, 2)
                cv2.circle(overlay, (x, y), 3, col, -1)
                if label:
                    (tw, th), _ = cv2.getTextSize(label, font, 0.45, 1)
                    lx, ly = x + 16, y + 5
                    sub = overlay[max(0, ly - th - 2):max(0, ly + 3), max(0, lx - 2):min(overlay.shape[1], lx + tw + 2)]
                    if sub.size > 0:
                        overlay[max(0, ly - th - 2):max(0, ly + 3), max(0, lx - 2):min(overlay.shape[1], lx + tw + 2)] = (sub * 0.3).astype(np.uint8)
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


def main():
    Path("logs").mkdir(exist_ok=True)
    Path("templates").mkdir(exist_ok=True)
    Path("config").mkdir(exist_ok=True)

    app = BotLauncher()
    app.mainloop()

if __name__ == "__main__":
    main()