import contextlib
import importlib.util
import io
import os
import re
import sys
import subprocess
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

if __name__ == "__main__" or __package__ is None:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))
    os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))
    from scripts.gui.config import REQUIRED_TEMPLATES, LIBS_DIR, _load_required_packages
else:
    from .config import REQUIRED_TEMPLATES, LIBS_DIR, _load_required_packages

_BG       = "#1e1e2e"
_BG_ALT   = "#252538"
_ACCENT   = "#7c6fff"
_ACCENT_HV= "#6a5de0"
_FG       = "#cdd6f4"
_FG_DIM   = "#888ca8"
_GREEN    = "#5a9e57"
_RED      = "#c45c6a"
_YELLOW   = "#b89b4a"
_BORDER   = "#393952"
_CARD_BG  = "#2a2a3d"

_MIN_PYTHON = (3, 8)
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
_dll_handles = []

def bootstrap_libs():
    libs = Path(LIBS_DIR)
    if not libs.exists():
        return
    for d in (libs, libs / "win32", libs / "win32com", libs / "win32comext"):
        s = str(d)
        if d.exists() and s not in sys.path:
            sys.path.insert(0, s)
    dll_dirs = set()
    for pyd in libs.rglob("*.pyd"):
        dll_dirs.add(pyd.parent)
    for dll in libs.rglob("*.dll"):
        dll_dirs.add(dll.parent)
    if getattr(sys, "frozen", False):
        internal = Path(sys.executable).parent / "_internal"
        if internal.exists():
            dll_dirs.add(internal)
            pywin32_sys32 = internal / "pywin32_system32"
            if pywin32_sys32.exists():
                dll_dirs.add(pywin32_sys32)
    for d in dll_dirs:
        try:
            if hasattr(os, "add_dll_directory"):
                handle = os.add_dll_directory(str(d))
                _dll_handles.append(handle)
            os.environ["PATH"] = str(d) + os.pathsep + os.environ.get("PATH", "")
        except Exception:
            pass

_CV2_PATCH_OLD = '    native_module = importlib.import_module("cv2")'
_CV2_PATCH_NEW = (
    '    import importlib.machinery as _imm, importlib.util as _imu, os as _os\n'
    '    _cv2_d = _os.path.dirname(_os.path.abspath(__file__))\n'
    '    _pyd = next((_f for _f in _os.listdir(_cv2_d) if _f.startswith("cv2") and _f.endswith(".pyd")), None)\n'
    '    if _pyd:\n'
    '        _ldr = _imm.ExtensionFileLoader("cv2", _os.path.join(_cv2_d, _pyd))\n'
    '        _spec = _imu.spec_from_loader("cv2", _ldr)\n'
    '        native_module = _imu.module_from_spec(_spec)\n'
    '        import sys as _sys\n'
    '        _sys.modules["cv2"] = native_module\n'
    '        _ldr.exec_module(native_module)\n'
    '    else:\n'
    '        native_module = importlib.import_module("cv2")'
)


def _patch_cv2_init():
    cv2_init = Path(LIBS_DIR) / 'cv2' / '__init__.py'
    if not cv2_init.exists():
        return
    text = cv2_init.read_text(encoding='utf-8')
    if _CV2_PATCH_OLD not in text:
        return
    cv2_init.write_text(text.replace(_CV2_PATCH_OLD, _CV2_PATCH_NEW), encoding='utf-8')


def preload_cv2():
    if 'cv2' in sys.modules:
        return
    if getattr(sys, 'frozen', False):
        return
    import importlib.machinery
    import importlib.util
    import ctypes as _ct
    cv2_dir = Path(LIBS_DIR) / 'cv2'
    if not cv2_dir.exists():
        return
    pyd = next(cv2_dir.glob('cv2*.pyd'), None)
    if not pyd:
        return
    for dll in cv2_dir.glob('*.dll'):
        try:
            _ct.WinDLL(str(dll))
        except Exception:
            pass
    loader = importlib.machinery.ExtensionFileLoader('cv2', str(pyd))
    spec = importlib.util.spec_from_loader('cv2', loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules['cv2'] = mod
    try:
        loader.exec_module(mod)
    except Exception:
        sys.modules.pop('cv2', None)
        raise


def _revert_cv2_patch():
    cv2_init = Path(LIBS_DIR) / 'cv2' / '__init__.py'
    if not cv2_init.exists():
        return
    text = cv2_init.read_text(encoding='utf-8')
    if _CV2_PATCH_NEW not in text:
        return
    cv2_init.write_text(text.replace(_CV2_PATCH_NEW, _CV2_PATCH_OLD), encoding='utf-8')

def _check_easyocr() -> bool:
    return importlib.util.find_spec("easyocr") is not None

def _check_python_version() -> bool:
    return sys.version_info >= _MIN_PYTHON

def _run_pywin32_postinstall():
    try:
        import shutil as _shutil
        libs = Path(LIBS_DIR)
        pysys32 = libs / "pywin32_system32"
        pysys32.mkdir(exist_ok=True)
        for candidate_dir in (libs / "pywin32_system32", libs / "win32"):
            if not candidate_dir.exists():
                continue
            for fname in os.listdir(candidate_dir):
                if fname.lower().endswith(".dll"):
                    src = candidate_dir / fname
                    dst = pysys32 / fname
                    if not dst.exists():
                        _shutil.copy2(str(src), str(dst))
        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(str(pysys32))
            except Exception:
                pass
        os.environ["PATH"] = str(pysys32) + os.pathsep + os.environ.get("PATH", "")
    except Exception:
        pass

def check_prerequisites():
    bootstrap_libs()
    issues = {
        "python_version": None,
        "python_packages": [],
        "easyocr": None,
        "templates": [],
    }
    if not _check_python_version():
        issues["python_version"] = (
            f"{sys.version_info.major}.{sys.version_info.minor}"
            f".{sys.version_info.micro}"
        )
    for module, pip_name in _load_required_packages().items():
        spec = importlib.util.find_spec(module)
        if spec is None and pip_name == "pywin32":
            _run_pywin32_postinstall()
            bootstrap_libs()
            spec = importlib.util.find_spec(module)
        if spec is None:
            issues["python_packages"].append(pip_name)
    if not _check_easyocr():
        issues["easyocr"] = "not_found"
    existing = set()
    for folder in (Path("templates"),):
        if folder.exists():
            existing.update(f.stem for f in folder.rglob("*.png"))
    if existing:
        for t in REQUIRED_TEMPLATES:
            if t not in existing:
                issues["templates"].append(t)
    else:
        issues["templates"] = list(REQUIRED_TEMPLATES)
    return issues

def _pip_run_with_progress(cmd, set_target, set_msg, on_done, on_error):
    last_real_error = ""
    collecting_count = 0
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_NO_WINDOW,
        )
        for raw in proc.stdout:
            line = raw.rstrip()
            if not line:
                continue
            if any(x in line for x in ["[notice]", "Notice:", "WARNING:"]):
                continue
            stripped = line.lstrip()
            lo = stripped.lower()
            if lo.startswith("collecting "):
                collecting_count += 1
                pkg = stripped.split()[1].split("-")[0].split("=")[0]
                target = min(5 + collecting_count * 1.8, 40)
                set_target(target)
                set_msg(f"Collecting {pkg}\u2026")
            elif lo.startswith("downloading "):
                pkg = stripped.split()[1].split("-")[0] if len(stripped.split()) > 1 else "package"
                m = re.search(r"\((\d+\.?\d*)\s*(GB|MB|kB)\)", stripped)
                if m:
                    val, unit = float(m.group(1)), m.group(2)
                    mb = val * 1024 if unit == "GB" else (val if unit == "MB" else val / 1024)
                    bonus = min(mb / 25.0, 40.0)
                    set_target(min(40 + bonus, 88))
                else:
                    set_target(min(40 + 8, 88))
                set_msg(f"Downloading {pkg}\u2026")
            elif "installing collected packages" in lo:
                set_target(93)
                set_msg("Installing\u2026")
            elif "successfully installed" in lo:
                set_target(100)
                set_msg("\u2713 Done!")
            elif "error" in lo and "warning" not in lo and "[notice]" not in lo:
                last_real_error = stripped
        proc.wait()
        if proc.returncode == 0:
            on_done()
        else:
            on_error(last_real_error or "Installation failed. Check your internet connection.")
    except Exception as exc:
        on_error(str(exc))

def _patch_distlib_finder():
    if not getattr(sys, "frozen", False):
        return
    try:
        import pip._vendor.distlib.resources as _res
        import pip._vendor.distlib as _dl

        distlib_dir = os.path.dirname(_dl.__file__)
        _orig_finder = _res.finder

        class _MinimalFinder:
            def __init__(self, module):
                self.module = module
                self.loader = None
                pkg_file = getattr(module, "__file__", "") or ""
                self.pkg_dir = os.path.dirname(pkg_file) if pkg_file else distlib_dir
                self.base = self.pkg_dir

            def find(self, resource_name):
                path = os.path.join(self.pkg_dir, resource_name)
                if os.path.exists(path):
                    class _FR:
                        def __init__(self, name, fpath):
                            self.name = name
                            self.path = fpath
                        @property
                        def bytes(self):
                            with open(self.path, 'rb') as f:
                                return f.read()
                    return _FR(resource_name, path)
                return None

            def iterator(self, resource_name):
                base = os.path.join(self.pkg_dir, resource_name) if resource_name else self.pkg_dir
                if not os.path.isdir(base):
                    return
                for fname in os.listdir(base):
                    r = self.find(os.path.join(resource_name, fname) if resource_name else fname)
                    if r is not None:
                        yield r

            def get_cache_info(self, resource):
                return None, None

        def _safe_finder(package):
            try:
                result = _orig_finder(package)
                if not hasattr(result, 'base'):
                    result.base = getattr(result, 'pkg_dir', distlib_dir)
                if not hasattr(result, 'iterator'):
                    pkg_dir = getattr(result, 'pkg_dir', distlib_dir)
                    def _iter(resource_name, _d=pkg_dir):
                        base = os.path.join(_d, resource_name) if resource_name else _d
                        if not os.path.isdir(base):
                            return
                        for fname in os.listdir(base):
                            fpath = os.path.join(base, fname)
                            class _FR:
                                def __init__(self, n, p):
                                    self.name = n
                                    self.path = p
                            yield _FR(fname, fpath)
                    result.iterator = _iter
                return result
            except Exception:
                mod = sys.modules.get(package)
                return _MinimalFinder(mod)

        _res.finder = _safe_finder

        scripts_path = os.path.join(distlib_dir, "scripts.py")
        modname = "pip._vendor.distlib.scripts"
        for key in list(sys.modules.keys()):
            if "distlib.scripts" in key:
                del sys.modules[key]
        if os.path.isfile(scripts_path):
            spec = importlib.util.spec_from_file_location(modname, scripts_path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[modname] = mod
            spec.loader.exec_module(mod)
    except Exception:
        pass

def _pip_run_frozen(pip_args, set_target, set_msg, on_done, on_error):
    result = {"ok": False, "err": ""}
    done_evt = threading.Event()

    def _run():
        try:
            _patch_distlib_finder()
            import pip._internal.cli.main as _pip_main
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                try:
                    rc = _pip_main.main(pip_args)
                    result["ok"] = (rc == 0)
                except SystemExit as e:
                    result["ok"] = (e.code == 0) if isinstance(e.code, int) else True
        except Exception as e:
            result["err"] = str(e)
        finally:
            done_evt.set()

    threading.Thread(target=_run, daemon=True).start()

    milestones = [
        (10, "Contacting PyPI\u2026"),
        (25, "Collecting packages\u2026"),
        (55, "Downloading\u2026"),
        (80, "Installing\u2026"),
        (92, "Finalizing\u2026"),
    ]
    prog = 2.0
    mi = 0
    while not done_evt.wait(0.6):
        if mi < len(milestones) and prog >= milestones[mi][0] - 6:
            set_msg(milestones[mi][1])
            mi += 1
        prog = min(prog + 1.0, 92)
        set_target(prog)

    if result["err"]:
        on_error(result["err"])
    elif result["ok"]:
        set_target(100)
        set_msg("\u2713 Done!")
        on_done()
    else:
        on_error("Installation failed. Check your internet connection.")

class PrerequisiteDialog(tk.Toplevel):

    def __init__(self, parent, issues):
        super().__init__(parent)
        self.withdraw()
        self.title("Mihono Bourbot \u2014 Prerequisites")
        self.geometry("700x580")
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
        py = parent.winfo_y() + (parent.winfo_height() - 580) // 2
        self.geometry(f"+{max(0, px)}+{max(0, py)}")
        self.deiconify()

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
        s.configure("Install.Horizontal.TProgressbar",
                    troughcolor=_BG_ALT, background=_ACCENT,
                    borderwidth=0, thickness=10)

    def _build(self, issues):
        hdr_frame = tk.Frame(self, bg=_BG)
        hdr_frame.pack(fill="x", padx=24, pady=(18, 4))
        tk.Label(
            hdr_frame, text="\u26A0  Prerequisites Check",
            font=("Segoe UI Bold", 14), bg=_BG, fg=_ACCENT,
        ).pack(side="left")
        tk.Label(
            self, text="The items below must be installed before the bot can run.",
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
        if issues.get("python_version"):
            self._build_python_version_card(issues["python_version"])
        if issues["python_packages"]:
            self._build_packages_card(issues["python_packages"])
        if issues["easyocr"]:
            self._build_easyocr_card()
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

    def _make_progress_block(self, body):
        prog_var = tk.DoubleVar(value=0)
        bar = ttk.Progressbar(
            body, variable=prog_var, maximum=100, length=480,
            style="Install.Horizontal.TProgressbar",
        )
        bar.pack(anchor="w", pady=(10, 2))
        status_lbl = tk.Label(
            body, text="", font=("Segoe UI", 9),
            bg=_CARD_BG, fg=_FG_DIM, anchor="w",
        )
        status_lbl.pack(anchor="w")
        return prog_var, status_lbl

    def _build_python_version_card(self, current_version):
        _, body = self._make_card(
            self._content, "Python Version Too Old", "\U0001F40D"
        )
        req = f"{_MIN_PYTHON[0]}.{_MIN_PYTHON[1]}"
        tk.Label(
            body,
            text=(
                f"Python {req}+ is required. You currently have Python {current_version}.\n"
                "Please download and install the latest Python version, then restart the bot."
            ),
            font=("Segoe UI", 10), bg=_CARD_BG, fg=_FG_DIM,
            anchor="w", justify="left",
        ).pack(anchor="w")
        btn_row = tk.Frame(body, bg=_CARD_BG)
        btn_row.pack(anchor="w", pady=(10, 0))
        ttk.Button(
            btn_row, text="\U0001F310  Download Python", style="Green.TButton",
            command=lambda: __import__("webbrowser").open(
                "https://www.python.org/downloads/"),
        ).pack(side="left")

    def _build_packages_card(self, packages):
        _, body = self._make_card(
            self._content, f"Missing Dependencies ({len(packages)})", "\U0001F4E6"
        )
        tk.Label(
            body,
            text="Some required components are missing and need to be installed.",
            font=("Segoe UI", 10), bg=_CARD_BG, fg=_FG_DIM, anchor="w",
        ).pack(anchor="w")
        for pkg in packages:
            tk.Label(
                body, text=f"  \u2022  {pkg}", font=("Consolas", 10),
                bg=_CARD_BG, fg=_FG_DIM, anchor="w",
            ).pack(anchor="w")
        prog_var, status_lbl = self._make_progress_block(body)
        btn_row = tk.Frame(body, bg=_CARD_BG)
        btn_row.pack(anchor="w", pady=(8, 0))
        self._pkg_btn = ttk.Button(
            btn_row, text="Install Automatically", style="Green.TButton",
            command=lambda: self._install_packages(packages, prog_var, status_lbl),
        )
        self._pkg_btn.pack(side="left")

    def _build_easyocr_card(self):
        _, body = self._make_card(
            self._content, "EasyOCR Not Installed", "\U0001F50D"
        )
        tk.Label(
            body,
            text=(
                "EasyOCR is required for reading in-game text.\n"
                "The installation is fully automatic \u2014 just click the button below."
            ),
            font=("Segoe UI", 10), bg=_CARD_BG, fg=_FG_DIM,
            anchor="w", justify="left",
        ).pack(anchor="w")
        tk.Label(body, text="\u26a0  This download is approximately ~800 MB. Internet connection required.", font=("Segoe UI", 9, "italic"), bg=_CARD_BG, fg=_YELLOW, anchor="w", justify="left").pack(anchor="w", pady=(4, 0))
        prog_var, status_lbl = self._make_progress_block(body)
        btn_row = tk.Frame(body, bg=_CARD_BG)
        btn_row.pack(anchor="w", pady=(8, 0))
        self._ocr_btn = ttk.Button(
            btn_row, text="Install Automatically", style="Green.TButton",
            command=lambda: self._install_easyocr(prog_var, status_lbl),
        )
        self._ocr_btn.pack(side="left")

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
        for t in missing[:8]:
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

    def _install_packages(self, packages, prog_var, status_lbl):
        self._pkg_btn.configure(state="disabled")
        state = {"pct": 0.0, "target": 2.0, "msg": "Starting\u2026", "done": False}

        def _animator():
            while not state["done"]:
                if state["pct"] < state["target"]:
                    diff = state["target"] - state["pct"]
                    step = max(0.05, diff * 0.05)
                    state["pct"] = min(state["pct"] + step, state["target"])
                    pct = state["pct"]
                    msg = state["msg"]
                    self.after(0, lambda p=pct, t=f"{msg} ({int(pct)}%)": (
                        prog_var.set(p),
                        status_lbl.configure(text=t, fg=_YELLOW),
                    ))
                time.sleep(0.15)

        threading.Thread(target=_animator, daemon=True).start()

        def _on_done():
            state["done"] = True
            _run_pywin32_postinstall()
            bootstrap_libs()
            _patch_cv2_init()
            self.after(0, lambda: (
                prog_var.set(100),
                status_lbl.configure(
                    text="\u2713 Done! Click Re-check to continue.", fg=_GREEN),
                self._pkg_btn.configure(state="normal"),
            ))

        def _on_error(msg):
            state["done"] = True
            self.after(0, lambda m=msg: (
                status_lbl.configure(text=f"\u2717 {m}", fg=_RED),
                self._pkg_btn.configure(state="normal"),
            ))

        os.makedirs(LIBS_DIR, exist_ok=True)

        if getattr(sys, "frozen", False):
            threading.Thread(
                target=_pip_run_frozen,
                args=(
                    [
                        "install",
                        "--target", LIBS_DIR,
                        "--ignore-installed",
                        "--no-user",
                        "--no-warn-script-location",
                        "--disable-pip-version-check",
                    ] + list(packages),
                    lambda t: state.update({"target": max(state["target"], t)}),
                    lambda m: state.update({"msg": m}),
                    _on_done,
                    _on_error,
                ),
                daemon=True,
            ).start()
        else:
            threading.Thread(
                target=_pip_run_with_progress,
                args=(
                    [
                        sys.executable, "-m", "pip", "install",
                        "--target", LIBS_DIR,
                        "--ignore-installed",
                    ] + list(packages),
                    lambda t: state.update({"target": max(state["target"], t)}),
                    lambda m: state.update({"msg": m}),
                    _on_done,
                    _on_error,
                ),
                daemon=True,
            ).start()

    def _install_easyocr(self, prog_var, status_lbl):
        self._ocr_btn.configure(state="disabled")
        state = {"pct": 0.0, "target": 1.0, "msg": "Preparing\u2026", "done": False}

        def _animator():
            while not state["done"]:
                if state["pct"] < state["target"]:
                    diff = state["target"] - state["pct"]
                    step = max(0.05, diff * 0.04)
                    state["pct"] = min(state["pct"] + step, state["target"])
                    pct = state["pct"]
                    msg = state["msg"]
                    self.after(0, lambda p=pct, t=f"{msg} ({int(pct)}%)": (
                        prog_var.set(p),
                        status_lbl.configure(text=t, fg=_YELLOW),
                    ))
                time.sleep(0.15)

        threading.Thread(target=_animator, daemon=True).start()

        def set_target(t):
            state["target"] = max(state["target"], t)

        def set_msg(m):
            state["msg"] = m

        def _on_done():
            state["done"] = True
            bootstrap_libs()
            _patch_cv2_init()
            self.after(0, lambda: (
                prog_var.set(100),
                status_lbl.configure(
                    text="\u2713 Done! Click Re-check to continue.", fg=_GREEN),
                self._ocr_btn.configure(state="normal"),
            ))

        def _on_error(msg):
            state["done"] = True
            if "WinError 5" in msg or "Access is denied" in msg:
                display = (
                    "Permission denied. Try running the bot as Administrator "
                    "(right-click \u2192 Run as administrator)."
                )
            else:
                display = msg or "Installation failed. Check your internet connection."
            self.after(0, lambda m=display: (
                status_lbl.configure(text=f"\u2717 {m}", fg=_RED),
                self._ocr_btn.configure(state="normal"),
            ))

        os.makedirs(LIBS_DIR, exist_ok=True)

        def _run():
            set_target(2)
            set_msg("Installing PyTorch (CPU)\u2026")
            torch_error = [None]

            if getattr(sys, "frozen", False):
                _pip_run_frozen(
                    [
                        "install",
                        "--target", LIBS_DIR,
                        "--ignore-installed",
                        "--no-user",
                        "--no-warn-script-location",
                        "--disable-pip-version-check",
                        "--index-url", "https://download.pytorch.org/whl/cpu",
                        "torch", "torchvision",
                    ],
                    lambda t: set_target(2 + t * 0.55),
                    set_msg,
                    lambda: None,
                    lambda e: torch_error.__setitem__(0, e),
                )
            else:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
                    capture_output=True, creationflags=_NO_WINDOW,
                )
                set_target(3)
                _pip_run_with_progress(
                    [
                        sys.executable, "-m", "pip", "install",
                        "--target", LIBS_DIR,
                        "--ignore-installed",
                        "--index-url", "https://download.pytorch.org/whl/cpu",
                        "torch", "torchvision",
                    ],
                    lambda t: set_target(3 + t * 0.55),
                    set_msg,
                    lambda: None,
                    lambda e: torch_error.__setitem__(0, e),
                )

            if torch_error[0]:
                _on_error(torch_error[0])
                return

            set_target(60)
            set_msg("Installing EasyOCR\u2026")

            if getattr(sys, "frozen", False):
                _pip_run_frozen(
                    [
                        "install",
                        "--target", LIBS_DIR,
                        "--ignore-installed",
                        "--no-user",
                        "--no-warn-script-location",
                        "--disable-pip-version-check",
                        "easyocr", "rapidfuzz",
                    ],
                    lambda t: set_target(60 + t * 0.40),
                    set_msg,
                    _on_done,
                    _on_error,
                )
            else:
                _pip_run_with_progress(
                    [
                        sys.executable, "-m", "pip", "install",
                        "--target", LIBS_DIR,
                        "--ignore-installed",
                        "easyocr", "rapidfuzz",
                    ],
                    lambda t: set_target(60 + t * 0.40),
                    set_msg,
                    _on_done,
                    _on_error,
                )

        threading.Thread(target=_run, daemon=True).start()

    def _capture_templates(self):
        tool_path = os.path.join("tools", "capture_templates.py")
        subprocess.Popen(
            [sys.executable, tool_path],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )

    def _recheck(self):
        new_issues = check_prerequisites()
        has_problems = (
            new_issues.get("python_version")
            or new_issues["python_packages"]
            or new_issues["easyocr"]
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
        issues.get("python_version")
        or issues["python_packages"]
        or issues["easyocr"]
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