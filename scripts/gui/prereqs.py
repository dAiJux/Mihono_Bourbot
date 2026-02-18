import os
import sys
import shutil
import subprocess
import threading
import urllib.request
import tempfile
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

if __name__ == "__main__" or __package__ is None:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))
    os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))
    from scripts.gui.config import TESSERACT_PATHS, REQUIRED_TEMPLATES, REQUIRED_PACKAGES
else:
    from .config import TESSERACT_PATHS, REQUIRED_TEMPLATES, REQUIRED_PACKAGES

_TESSERACT_URL = (
    "https://github.com/UB-Mannheim/tesseract/releases/download/"
    "v5.5.0/tesseract-ocr-w64-setup-5.5.0.20241111.exe"
)

def _find_tesseract():
    t = shutil.which("tesseract")
    if t:
        return t
    user = os.environ.get("USERNAME", "")
    for p in TESSERACT_PATHS:
        real = p.replace("{user}", user)
        if os.path.isfile(real):
            return real
    return None

def prompt_user(message, default=True):
    root = tk._default_root
    if root is None:
        root = tk.Tk()
        root.withdraw()
    return messagebox.askyesno(
        "Mihono Bourbot", message, default="yes" if default else "no"
    )

def check_prerequisites():
    issues = {"python_packages": [], "tesseract": None, "templates": []}

    for module, pip_name in REQUIRED_PACKAGES.items():
        try:
            __import__(module)
        except ImportError:
            issues["python_packages"].append(pip_name)

    if not _find_tesseract():
        issues["tesseract"] = "not_found"

    templates_dir = Path("templates")
    if templates_dir.exists():
        existing = {f.stem for f in templates_dir.rglob("*.png")}
        for t in REQUIRED_TEMPLATES:
            if t not in existing:
                issues["templates"].append(t)
    else:
        issues["templates"] = list(REQUIRED_TEMPLATES)

    return issues

_BG        = "#1e1e2e"
_BG_ALT    = "#252538"
_ACCENT    = "#7c6fff"
_ACCENT_HV = "#6a5de0"
_FG        = "#cdd6f4"
_FG_DIM    = "#888ca8"
_GREEN     = "#5a9e57"
_RED       = "#c45c6a"
_YELLOW    = "#b89b4a"
_BORDER    = "#393952"
_CARD_BG   = "#2a2a3d"

class PrerequisiteDialog(tk.Toplevel):

    def __init__(self, parent, issues):
        super().__init__(parent)
        self.title("Mihono Bourbot \u2014 Prerequisites")
        self.geometry("700x560")
        self.resizable(False, False)
        self.configure(bg=_BG)
        self.transient(parent)
        self.grab_set()
        self.result = "cancel"
        self.issues = issues

        self._setup_styles()
        self._build(issues)

        self.update_idletasks()
        px = parent.winfo_x() + (parent.winfo_width() - 700) // 2
        py = parent.winfo_y() + (parent.winfo_height() - 560) // 2
        self.geometry(f"+{max(0, px)}+{max(0, py)}")

    def _setup_styles(self):
        s = ttk.Style(self)
        s.configure("Prereq.TFrame", background=_BG)
        s.configure("Card.TFrame", background=_CARD_BG)
        s.configure("Prereq.TLabel", background=_BG, foreground=_FG,
                     font=("Segoe UI", 10))
        s.configure("Card.TLabel", background=_CARD_BG, foreground=_FG,
                     font=("Segoe UI", 10))
        s.configure("CardDim.TLabel", background=_CARD_BG, foreground=_FG_DIM,
                     font=("Segoe UI", 9))
        s.configure("Header.TLabel", background=_BG, foreground=_ACCENT,
                     font=("Segoe UI Bold", 14))
        s.configure("SubHeader.TLabel", background=_CARD_BG, foreground=_FG,
                     font=("Segoe UI Semibold", 11))

        s.configure("Prereq.TButton", background=_ACCENT, foreground="#ffffff",
                     font=("Segoe UI Semibold", 10), padding=[14, 5],
                     borderwidth=0)
        s.map("Prereq.TButton",
              background=[("active", _ACCENT_HV), ("pressed", _ACCENT_HV)])

        s.configure("Green.TButton", background=_GREEN, foreground="#ffffff",
                     font=("Segoe UI Semibold", 10), padding=[14, 5],
                     borderwidth=0)
        s.map("Green.TButton",
              background=[("active", "#4d8a4b"), ("pressed", "#4d8a4b")])

        s.configure("Dim.TButton", background=_BG_ALT, foreground=_FG_DIM,
                     font=("Segoe UI", 10), padding=[14, 5], borderwidth=0)
        s.map("Dim.TButton",
              background=[("active", _BORDER), ("pressed", _BORDER)])

        s.configure("Prereq.Horizontal.TProgressbar",
                     troughcolor=_BG_ALT, background=_ACCENT,
                     borderwidth=0, thickness=8)

    def _build(self, issues):
        hdr_frame = tk.Frame(self, bg=_BG)
        hdr_frame.pack(fill="x", padx=24, pady=(18, 4))
        tk.Label(
            hdr_frame, text="\u26A0  Prerequisites Check",
            font=("Segoe UI Bold", 14), bg=_BG, fg=_ACCENT,
        ).pack(side="left")

        tk.Label(
            self, text="Some items need attention before the bot can run.",
            font=("Segoe UI", 10), bg=_BG, fg=_FG_DIM,
        ).pack(anchor="w", padx=24, pady=(0, 12))

        container = tk.Frame(self, bg=_BG)
        container.pack(fill="both", expand=True, padx=24, pady=(0, 8))

        canvas = tk.Canvas(container, bg=_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical",
                                  command=canvas.yview)
        self._content = tk.Frame(canvas, bg=_BG)
        self._content.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=self._content, anchor="nw",
                             width=640)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        self.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

        if issues["python_packages"]:
            self._build_packages_card(issues["python_packages"])
        if issues["tesseract"]:
            self._build_tesseract_card()
        if issues["templates"]:
            self._build_templates_card(issues["templates"])

        btn_frame = tk.Frame(self, bg=_BG)
        btn_frame.pack(fill="x", padx=24, pady=(4, 16))

        ttk.Button(
            btn_frame, text="Re-check", style="Prereq.TButton",
            command=self._recheck,
        ).pack(side="right", padx=(8, 0))

        ttk.Button(
            btn_frame, text="Continue Anyway", style="Dim.TButton",
            command=self._continue,
        ).pack(side="right")

    def _make_card(self, parent, title, icon="\u25CF"):
        card = tk.Frame(parent, bg=_CARD_BG, highlightbackground=_BORDER,
                        highlightthickness=1)
        card.pack(fill="x", pady=(0, 10))

        inner = tk.Frame(card, bg=_CARD_BG)
        inner.pack(fill="x", padx=16, pady=12)

        tk.Label(
            inner, text=f"{icon}  {title}",
            font=("Segoe UI Semibold", 11), bg=_CARD_BG, fg=_FG,
        ).pack(anchor="w")

        body = tk.Frame(inner, bg=_CARD_BG)
        body.pack(fill="x", anchor="w", pady=(6, 0))
        return card, body

    def _build_packages_card(self, packages):
        _, body = self._make_card(
            self._content, "Missing Python Packages", "\U0001F4E6"
        )

        for pkg in packages:
            tk.Label(
                body, text=f"  \u2022  {pkg}", font=("Consolas", 10),
                bg=_CARD_BG, fg=_FG_DIM, anchor="w",
            ).pack(anchor="w")

        tk.Label(
            body,
            text=f"\nFix:  pip install {' '.join(packages)}",
            font=("Consolas", 9), bg=_CARD_BG, fg=_FG_DIM, anchor="w",
        ).pack(anchor="w", pady=(4, 0))

        btn_row = tk.Frame(body, bg=_CARD_BG)
        btn_row.pack(anchor="w", pady=(8, 0))
        self._pkg_btn = ttk.Button(
            btn_row, text="Install Packages", style="Green.TButton",
            command=self._install_packages,
        )
        self._pkg_btn.pack(side="left")
        self._pkg_status = tk.Label(
            btn_row, text="", font=("Segoe UI", 9),
            bg=_CARD_BG, fg=_FG_DIM,
        )
        self._pkg_status.pack(side="left", padx=(12, 0))

    def _build_tesseract_card(self):
        _, body = self._make_card(
            self._content, "Tesseract OCR Not Found", "\U0001F50D"
        )

        tk.Label(
            body,
            text=(
                "Tesseract is required for reading in-game text.\n"
                "Click the button below to download and install it\n"
                "automatically."
            ),
            font=("Segoe UI", 10), bg=_CARD_BG, fg=_FG_DIM,
            anchor="w", justify="left",
        ).pack(anchor="w")

        self._tess_progress_frame = tk.Frame(body, bg=_CARD_BG)
        self._tess_progress_frame.pack(fill="x", pady=(8, 0))

        self._tess_progress = ttk.Progressbar(
            self._tess_progress_frame,
            style="Prereq.Horizontal.TProgressbar",
            orient="horizontal", length=400, mode="determinate",
        )
        self._tess_progress_label = tk.Label(
            self._tess_progress_frame, text="",
            font=("Segoe UI", 9), bg=_CARD_BG, fg=_FG_DIM,
        )

        btn_row = tk.Frame(body, bg=_CARD_BG)
        btn_row.pack(anchor="w", pady=(8, 0))
        self._tess_btn = ttk.Button(
            btn_row, text="Download & Install Tesseract",
            style="Green.TButton", command=self._install_tesseract,
        )
        self._tess_btn.pack(side="left")
        self._tess_status = tk.Label(
            btn_row, text="", font=("Segoe UI", 9),
            bg=_CARD_BG, fg=_FG_DIM,
        )
        self._tess_status.pack(side="left", padx=(12, 0))

        tk.Label(
            body,
            text=(
                "Or install manually:\n"
                "  winget install UB-Mannheim.TesseractOCR"
            ),
            font=("Consolas", 9), bg=_CARD_BG, fg=_FG_DIM,
            anchor="w", justify="left",
        ).pack(anchor="w", pady=(10, 0))

    def _build_templates_card(self, missing):
        n_miss = len(missing)
        n_total = len(REQUIRED_TEMPLATES)
        _, body = self._make_card(
            self._content,
            f"Missing Templates ({n_miss}/{n_total})",
            "\U0001F5BC",
        )

        tk.Label(
            body,
            text=(
                "Templates are small screenshots of game UI elements\n"
                "the bot uses to recognise the current screen."
            ),
            font=("Segoe UI", 10), bg=_CARD_BG, fg=_FG_DIM,
            anchor="w", justify="left",
        ).pack(anchor="w")

        show = missing[:8]
        for t in show:
            tk.Label(
                body, text=f"  \u2022  {t}.png", font=("Consolas", 10),
                bg=_CARD_BG, fg=_FG_DIM, anchor="w",
            ).pack(anchor="w")
        if len(missing) > 8:
            tk.Label(
                body,
                text=f"  \u2026 and {len(missing) - 8} more",
                font=("Segoe UI", 9, "italic"), bg=_CARD_BG, fg=_FG_DIM,
            ).pack(anchor="w")

        btn_row = tk.Frame(body, bg=_CARD_BG)
        btn_row.pack(anchor="w", pady=(8, 0))
        ttk.Button(
            btn_row, text="Capture Templates", style="Green.TButton",
            command=self._capture_templates,
        ).pack(side="left")

    def _install_packages(self):
        pkgs = self.issues["python_packages"]
        cmd = [sys.executable, "-m", "pip", "install", "--user"] + pkgs
        self._pkg_btn.configure(state="disabled")
        self._pkg_status.configure(text="Installing\u2026", fg=_YELLOW)

        def _thread():
            try:
                subprocess.run(
                    cmd, check=True, capture_output=True, text=True,
                    timeout=120,
                )
                self.after(0, lambda: self._pkg_status.configure(
                    text="\u2713 Installed", fg=_GREEN))
            except Exception as e:
                msg = str(e)[:60]
                self.after(0, lambda: self._pkg_status.configure(
                    text=f"\u2717 Failed: {msg}", fg=_RED))
            finally:
                self.after(0, lambda: self._pkg_btn.configure(state="normal"))

        threading.Thread(target=_thread, daemon=True).start()

    def _install_tesseract(self):
        self._tess_btn.configure(state="disabled")
        self._tess_status.configure(text="Downloading\u2026", fg=_YELLOW)
        self._tess_progress.pack(fill="x")
        self._tess_progress_label.pack(anchor="w", pady=(4, 0))
        self._tess_progress["value"] = 0

        def _update_progress(downloaded, total):
            if total > 0:
                pct = downloaded / total * 100
                mb_dl = downloaded / (1024 * 1024)
                mb_tot = total / (1024 * 1024)
                txt = f"{mb_dl:.1f} / {mb_tot:.1f} MB  ({pct:.0f}%)"
                self.after(0, lambda p=pct, t=txt: (
                    self._tess_progress.configure(value=p),
                    self._tess_progress_label.configure(text=t),
                ))
            else:
                mb_dl = downloaded / (1024 * 1024)
                txt = f"{mb_dl:.1f} MB downloaded\u2026"
                self.after(0, lambda t=txt: (
                    self._tess_progress.configure(mode="indeterminate"),
                    self._tess_progress_label.configure(text=t),
                ))

        def _thread():
            try:
                tmp = os.path.join(
                    tempfile.gettempdir(), "tesseract_setup.exe"
                )
                req = urllib.request.urlopen(_TESSERACT_URL, timeout=60)
                total = int(req.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 64 * 1024

                with open(tmp, "wb") as f:
                    while True:
                        chunk = req.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        _update_progress(downloaded, total)

                self.after(0, lambda: self._tess_progress.configure(value=100))
                self.after(0, lambda: self._tess_status.configure(
                    text="Running installer\u2026", fg=_YELLOW))
                self.after(0, lambda: self._tess_progress_label.configure(
                    text="The installer window may appear behind this one."))

                result = subprocess.run(
                    [tmp, "/S"],
                    capture_output=True, text=True, timeout=300,
                )

                if result.returncode == 0:
                    self.after(0, lambda: self._tess_status.configure(
                        text="\u2713 Installed \u2014 click Re-check",
                        fg=_GREEN,
                    ))
                    self.after(0, lambda: self._tess_progress_label.configure(
                        text="Tesseract installed. Click Re-check to verify.",
                    ))
                else:
                    self.after(0, lambda: self._tess_status.configure(
                        text="Installer finished (click Re-check)", fg=_YELLOW,
                    ))
                    self.after(0, lambda: self._tess_progress_label.configure(
                        text="Click Re-check to verify.",
                    ))

                try:
                    os.remove(tmp)
                except OSError:
                    pass

            except Exception as e:
                err = str(e)[:80]
                self.after(0, lambda: self._tess_status.configure(
                    text=f"\u2717 {err}", fg=_RED))
                self.after(0, lambda: self._tess_progress_label.configure(
                    text="Try: winget install UB-Mannheim.TesseractOCR",
                ))
            finally:
                self.after(0, lambda: self._tess_btn.configure(state="normal"))

        threading.Thread(target=_thread, daemon=True).start()

    def _capture_templates(self):
        tool_path = os.path.join("tools", "capture_templates.py")
        subprocess.Popen(
            [sys.executable, tool_path],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )

    def _recheck(self):
        new_issues = check_prerequisites()
        has_problems = (
            new_issues["python_packages"]
            or new_issues["tesseract"]
            or new_issues["templates"]
        )
        if not has_problems:
            for w in self._content.winfo_children():
                w.destroy()

            success_frame = tk.Frame(self._content, bg=_BG)
            success_frame.pack(fill="both", expand=True, pady=40)
            tk.Label(
                success_frame, text="\u2713",
                font=("Segoe UI", 48), bg=_BG, fg=_GREEN,
            ).pack()
            tk.Label(
                success_frame, text="All prerequisites met!",
                font=("Segoe UI Semibold", 14), bg=_BG, fg=_GREEN,
            ).pack(pady=(8, 0))

            self.result = "ok"
            self.after(1200, self.destroy)
        else:
            self.issues = new_issues
            for w in self.winfo_children():
                w.destroy()
            self._build(new_issues)

    def _continue(self):
        self.result = "continue"
        self.destroy()

if __name__ == "__main__":
    issues = check_prerequisites()
    has_problems = (
        issues["python_packages"]
        or issues["tesseract"]
        or issues["templates"]
    )
    if has_problems:
        root = tk.Tk()
        root.withdraw()
        dlg = PrerequisiteDialog(root, issues)
        root.wait_window(dlg)
        root.destroy()
    else:
        print("All prerequisites met.")