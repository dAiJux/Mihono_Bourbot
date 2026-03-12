import json
import os
import sys
import threading
import zipfile
import shutil
import tempfile
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from urllib.request import urlopen, Request

try:
    from _token_data import _ENC, _KEY  # type: ignore[import]
    _TOKEN = bytes(b ^ k for b, k in zip(_ENC, _KEY)).decode("utf-8")
except ImportError:
    _TOKEN = None

RELEASES_API = "https://api.github.com/repos/dAiJux/Mihono_Bourbot/releases/latest"
VERSION_FILE = "version.txt"

if getattr(sys, "frozen", False):
    _BOT_DIR = Path(sys.executable).parent
else:
    _BOT_DIR = Path(os.path.abspath(__file__)).parent

_BG      = "#1e1e2e"
_BG_ALT  = "#252538"
_ACCENT  = "#7c6fff"
_FG      = "#cdd6f4"
_FG_DIM  = "#888ca8"
_GREEN   = "#5a9e57"
_BORDER  = "#393952"

def get_current_version():
    vf = _BOT_DIR / VERSION_FILE
    if vf.exists():
        return vf.read_text(encoding="utf-8").strip()
    return "0.0.0"

def _version_tuple(v):
    try:
        return tuple(int(x) for x in v.lstrip("v").split("."))
    except Exception:
        return (0, 0, 0)

def _api_request(url, timeout=8):
    headers = {"User-Agent": "MihonoBourbot-Updater"}
    if _TOKEN:
        headers["Authorization"] = f"token {_TOKEN}"
    req = Request(url, headers=headers)
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def check_for_update():
    try:
        data = _api_request(RELEASES_API)
        tag = data.get("tag_name", "0.0.0")
        if _version_tuple(tag) > _version_tuple(get_current_version()):
            assets = data.get("assets", [])
            zip_asset = next((a for a in assets if a["name"].endswith(".zip")), None)
            if zip_asset:
                return {
                    "tag": tag,
                    "notes": data.get("body", ""),
                    "url": zip_asset["url"],
                    "size": zip_asset["size"],
                }
    except Exception:
        pass
    return None

class UpdateDialog(tk.Toplevel):

    def __init__(self, parent, info):
        super().__init__(parent)
        self.title("Update Available")
        self.geometry("520x340")
        self.resizable(False, False)
        self.configure(bg=_BG)
        self.transient(parent)
        self.grab_set()
        self.result = "skip"
        self._info = info
        self._build(info)
        self.update_idletasks()
        px = parent.winfo_x() + (parent.winfo_width() - 520) // 2
        py = parent.winfo_y() + (parent.winfo_height() - 340) // 2
        self.geometry(f"+{max(0,px)}+{max(0,py)}")

    def _build(self, info):
        tk.Label(self, text="A new update is available!",
                 font=("Segoe UI Bold", 13), bg=_BG, fg=_ACCENT).pack(pady=(18, 4))
        tk.Label(self, text=f"{get_current_version()}  \u2192  {info['tag']}",
                 font=("Segoe UI", 11), bg=_BG, fg=_FG).pack(pady=(0, 10))
        tk.Frame(self, height=1, bg=_BORDER).pack(fill="x", padx=16)

        nf = tk.Frame(self, bg=_BG_ALT)
        nf.pack(fill="both", expand=True, padx=16, pady=10)
        nt = tk.Text(nf, font=("Segoe UI", 9), bg=_BG_ALT, fg=_FG_DIM,
                     relief="flat", wrap="word", height=6, bd=0)
        nt.pack(fill="both", expand=True, padx=8, pady=6)
        nt.insert("1.0", info["notes"] or "No release notes.")
        nt.configure(state="disabled")

        mb = info["size"] / 1_048_576
        tk.Label(self, text=f"Download size: ~{mb:.1f} MB",
                 font=("Segoe UI", 9), bg=_BG, fg=_FG_DIM).pack(pady=(0, 6))

        self._prog_var = tk.DoubleVar(value=0)
        self._prog_lbl = tk.StringVar(value="")
        style = ttk.Style(self)
        style.configure("Up.Horizontal.TProgressbar",
                         troughcolor=_BG_ALT, background=_ACCENT, thickness=6)
        ttk.Progressbar(self, variable=self._prog_var,
                        style="Up.Horizontal.TProgressbar",
                        maximum=100, length=480).pack(padx=16, pady=(0, 2))
        tk.Label(self, textvariable=self._prog_lbl,
                 font=("Consolas", 8), bg=_BG, fg=_FG_DIM).pack()

        bf = tk.Frame(self, bg=_BG)
        bf.pack(pady=10)
        self._update_btn = tk.Button(
            bf, text="Update Now", command=self._start_update,
            bg=_ACCENT, fg="white", relief="flat",
            font=("Segoe UI Bold", 10), padx=20, pady=6,
            activebackground="#6a5de0", cursor="hand2")
        self._update_btn.pack(side="left", padx=6)
        tk.Button(bf, text="Skip", command=self._skip,
                  bg=_BG_ALT, fg=_FG_DIM, relief="flat",
                  font=("Segoe UI", 10), padx=16, pady=6,
                  activebackground=_BORDER).pack(side="left", padx=6)

    def _skip(self):
        self.result = "skip"
        self.destroy()

    def _start_update(self):
        self._update_btn.configure(state="disabled")
        threading.Thread(target=self._do_update, daemon=True).start()

    def _set_prog(self, pct, msg=""):
        self.after(0, lambda: (self._prog_var.set(pct), self._prog_lbl.set(msg)))

    def _do_update(self):
        try:
            self._set_prog(2, "Downloading update...")
            tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
            tmp.close()

            headers = {"User-Agent": "MihonoBourbot-Updater", "Accept": "application/octet-stream"}
            if _TOKEN:
                headers["Authorization"] = f"token {_TOKEN}"

            total = self._info["size"]
            downloaded = 0
            req = Request(self._info["url"], headers=headers)
            with urlopen(req, timeout=60) as resp, open(tmp.name, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = min(downloaded / total * 80, 80)
                        self._set_prog(pct, f"Downloading... {downloaded//1024} / {total//1024} KB")

            self._set_prog(82, "Extracting...")
            extract_dir = tempfile.mkdtemp(prefix="mihono_update_")
            with zipfile.ZipFile(tmp.name, "r") as zf:
                zf.extractall(extract_dir)
            os.unlink(tmp.name)

            self._set_prog(88, "Installing files...")
            root_dir = _BOT_DIR
            src_root = Path(extract_dir)
            inner = list(src_root.iterdir())
            if len(inner) == 1 and inner[0].is_dir():
                src_root = inner[0]

            SKIP_DIRS = {"libs", "logs", "_internal"}
            SKIP_FILES = {"Updater.exe", "Mihono Bourbot.exe"}

            new_templates = set()
            for item in src_root.rglob("*.png"):
                rel = item.relative_to(src_root)
                if rel.parts[0] == "templates":
                    new_templates.add(rel.as_posix())

            for item in src_root.rglob("*"):
                if item.is_dir():
                    continue
                rel = item.relative_to(src_root)
                if rel.parts[0] in SKIP_DIRS:
                    continue
                if item.name in SKIP_FILES:
                    continue
                dst = root_dir / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                try:
                    if item.suffix == ".json" and dst.exists():
                        self._merge_json(item, dst)
                    else:
                        shutil.copy2(str(item), str(dst))
                except Exception:
                    pass

            shutil.rmtree(extract_dir, ignore_errors=True)

            tpl_dir = root_dir / "templates"
            if tpl_dir.is_dir() and new_templates:
                for old_png in tpl_dir.rglob("*.png"):
                    rel = old_png.relative_to(root_dir).as_posix()
                    if rel not in new_templates:
                        try:
                            old_png.unlink()
                        except Exception:
                            pass

            (root_dir / VERSION_FILE).write_text(self._info["tag"], encoding="utf-8")

            self._set_prog(100, f"Updated to {self._info['tag']}! Restart to apply.")
            self.result = "updated"
            self.after(0, self._show_restart)

        except Exception as e:
            self.after(0, lambda err=e: self._prog_lbl.set(f"Error: {err}"))
            self.after(0, lambda: self._update_btn.configure(state="normal"))

    def _merge_json(self, src_path, dst_path):
        try:
            with open(src_path, "r", encoding="utf-8") as f:
                new_data = json.loads(f.read())
            with open(dst_path, "r", encoding="utf-8") as f:
                old_data = json.loads(f.read())
            merged = self._deep_merge(new_data, old_data)
            with open(dst_path, "w", encoding="utf-8") as f:
                json.dump(merged, f, ensure_ascii=False, indent=2)
        except Exception:
            shutil.copy2(str(src_path), str(dst_path))

    def _deep_merge(self, new, old):
        if not isinstance(new, dict) or not isinstance(old, dict):
            return old
        result = dict(old)
        for k, v in new.items():
            if k in old:
                result[k] = self._deep_merge(v, old[k])
            else:
                result[k] = v
        return result

    def _show_restart(self):
        for w in self.winfo_children():
            if isinstance(w, tk.Frame):
                btns = [c for c in w.winfo_children() if isinstance(c, tk.Button)]
                if btns:
                    for c in w.winfo_children():
                        c.destroy()
                    tk.Button(w, text="Restart Now", command=self._restart,
                              bg=_GREEN, fg="white", relief="flat",
                              font=("Segoe UI Bold", 10), padx=20, pady=6,
                              cursor="hand2").pack()
                    break

    def _restart(self):
        self.destroy()
        os.execv(sys.executable, [sys.executable] + sys.argv)

def check_update_async(parent):
    def _check():
        info = check_for_update()
        if info:
            parent.after(0, lambda: _show(info))

    def _show(info):
        dlg = UpdateDialog(parent, info)
        parent.wait_window(dlg)

    threading.Thread(target=_check, daemon=True).start()

def _run_standalone():
    root = tk.Tk()
    root.withdraw()
    root.configure(bg=_BG)

    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()

    win = tk.Toplevel(root)
    win.title("Mihono Bourbot — Updater")
    win.geometry("560x120")
    win.resizable(False, False)
    win.configure(bg=_BG)
    win.protocol("WM_DELETE_WINDOW", root.destroy)
    win.geometry(f"+{(sw - 560) // 2}+{(sh - 120) // 2}")

    tk.Label(
        win, text="Checking for updates…",
        font=("Segoe UI", 11), bg=_BG, fg=_FG,
    ).pack(expand=True)

    style = ttk.Style(win)
    style.configure("Up.Horizontal.TProgressbar",
                     troughcolor=_BG_ALT, background=_ACCENT, thickness=4)
    bar = ttk.Progressbar(win, style="Up.Horizontal.TProgressbar",
                          mode="indeterminate", length=500)
    bar.pack(pady=(0, 16))
    bar.start(12)

    def _clear_win():
        for w in win.winfo_children():
            w.destroy()

    def _show_up_to_date():
        win.geometry("560x140")
        win.geometry(f"+{(sw - 560) // 2}+{(sh - 140) // 2}")
        _clear_win()
        tk.Label(
            win, text="\u2713  You are up to date!",
            font=("Segoe UI Semibold", 13), bg=_BG, fg=_GREEN,
        ).pack(pady=(28, 6))
        tk.Label(
            win, text=f"Current version: {get_current_version()}",
            font=("Segoe UI", 9), bg=_BG, fg=_FG_DIM,
        ).pack()
        tk.Button(
            win, text="Close", command=root.destroy,
            bg=_BG_ALT, fg=_FG_DIM, relief="flat",
            font=("Segoe UI", 10), padx=20, pady=5,
            activebackground=_BORDER, cursor="hand2",
        ).pack(pady=(12, 0))

    def _show_update(info):
        win.geometry("560x420")
        win.geometry(f"+{(sw - 560) // 2}+{(sh - 420) // 2}")
        _clear_win()

        tk.Label(
            win, text="\u26A0  Update Available!",
            font=("Segoe UI Bold", 13), bg=_BG, fg=_ACCENT,
        ).pack(pady=(18, 2))
        tk.Label(
            win, text=f"{get_current_version()}  \u2192  {info['tag']}",
            font=("Segoe UI", 11), bg=_BG, fg=_FG,
        ).pack(pady=(0, 8))
        tk.Frame(win, height=1, bg=_BORDER).pack(fill="x", padx=16)

        notes_frame = tk.Frame(win, bg=_BG_ALT)
        notes_frame.pack(fill="both", expand=True, padx=16, pady=10)
        nt = tk.Text(
            notes_frame, font=("Segoe UI", 9), bg=_BG_ALT, fg=_FG_DIM,
            relief="flat", wrap="word", height=8, bd=0,
        )
        nt.pack(fill="both", expand=True, padx=8, pady=6)
        nt.insert("1.0", info["notes"] or "No release notes.")
        nt.configure(state="disabled")

        mb = info["size"] / 1_048_576
        tk.Label(
            win, text=f"Download size: ~{mb:.1f} MB",
            font=("Segoe UI", 9), bg=_BG, fg=_FG_DIM,
        ).pack()

        prog_var = tk.DoubleVar(value=0)
        prog_lbl = tk.StringVar(value="")
        ttk.Progressbar(
            win, variable=prog_var, style="Up.Horizontal.TProgressbar",
            maximum=100, length=520,
        ).pack(padx=16, pady=(6, 2))
        tk.Label(win, textvariable=prog_lbl,
                 font=("Consolas", 8), bg=_BG, fg=_FG_DIM).pack()

        btn_row = tk.Frame(win, bg=_BG)
        btn_row.pack(pady=8)

        update_btn = tk.Button(
            btn_row, text="Update Now",
            bg=_ACCENT, fg="white", relief="flat",
            font=("Segoe UI Bold", 10), padx=20, pady=6,
            activebackground="#6a5de0", cursor="hand2",
        )
        update_btn.pack(side="left", padx=6)
        tk.Button(
            btn_row, text="Skip", command=root.destroy,
            bg=_BG_ALT, fg=_FG_DIM, relief="flat",
            font=("Segoe UI", 10), padx=16, pady=6,
            activebackground=_BORDER,
        ).pack(side="left", padx=6)

        _state = {"running": False}

        def _do_update():
            if _state["running"]:
                return
            _state["running"] = True
            update_btn.configure(state="disabled")

            def _set_prog(pct, msg=""):
                win.after(0, lambda: (prog_var.set(pct), prog_lbl.set(msg)))

            def _run():
                try:
                    import tempfile, zipfile as zf_mod
                    _set_prog(2, "Downloading update...")
                    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
                    tmp.close()
                    headers = {"User-Agent": "MihonoBourbot-Updater", "Accept": "application/octet-stream"}
                    if _TOKEN:
                        headers["Authorization"] = f"token {_TOKEN}"
                    total = info["size"]
                    downloaded = 0
                    req = Request(info["url"], headers=headers)
                    with urlopen(req, timeout=60) as resp, open(tmp.name, "wb") as f:
                        while True:
                            chunk = resp.read(65536)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total:
                                _set_prog(
                                    min(downloaded / total * 80, 80),
                                    f"Downloading... {downloaded // 1024} / {total // 1024} KB",
                                )
                    _set_prog(82, "Extracting...")
                    extract_dir = tempfile.mkdtemp(prefix="mihono_update_")
                    with zf_mod.ZipFile(tmp.name, "r") as z:
                        z.extractall(extract_dir)
                    os.unlink(tmp.name)
                    _set_prog(88, "Installing files...")
                    root_dir = _BOT_DIR
                    src_root = Path(extract_dir)
                    inner = list(src_root.iterdir())
                    if len(inner) == 1 and inner[0].is_dir():
                        src_root = inner[0]
                    SKIP_DIRS = {"libs", "logs", "_internal"}
                    SKIP_FILES = {"Updater.exe", "Mihono Bourbot.exe"}
                    new_templates = set()
                    for item in src_root.rglob("*.png"):
                        rel = item.relative_to(src_root)
                        if rel.parts[0] == "templates":
                            new_templates.add(rel.as_posix())
                    for item in src_root.rglob("*"):
                        if item.is_dir():
                            continue
                        rel = item.relative_to(src_root)
                        if rel.parts[0] in SKIP_DIRS:
                            continue
                        if item.name in SKIP_FILES:
                            continue
                        dst = root_dir / rel
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        try:
                            if item.suffix == ".json" and dst.exists():
                                with open(item, "r", encoding="utf-8") as f:
                                    new_d = json.loads(f.read())
                                with open(dst, "r", encoding="utf-8") as f:
                                    old_d = json.loads(f.read())
                                def _merge(n, o):
                                    if not isinstance(n, dict) or not isinstance(o, dict):
                                        return o
                                    r = dict(o)
                                    for k, v in n.items():
                                        if k in o:
                                            r[k] = _merge(v, o[k])
                                        else:
                                            r[k] = v
                                    return r
                                with open(dst, "w", encoding="utf-8") as f:
                                    json.dump(_merge(new_d, old_d), f, ensure_ascii=False, indent=2)
                            else:
                                shutil.copy2(str(item), str(dst))
                        except Exception:
                            pass
                    tpl_dir = root_dir / "templates"
                    if tpl_dir.is_dir() and new_templates:
                        for old_png in tpl_dir.rglob("*.png"):
                            rel = old_png.relative_to(root_dir).as_posix()
                            if rel not in new_templates:
                                try:
                                    old_png.unlink()
                                except Exception:
                                    pass
                    shutil.rmtree(extract_dir, ignore_errors=True)
                    (root_dir / VERSION_FILE).write_text(info["tag"], encoding="utf-8")
                    _set_prog(100, f"Updated to {info['tag']}!")
                    win.after(0, _show_done)
                except Exception as e:
                    win.after(0, lambda err=e: (
                        prog_lbl.set(f"Error: {err}"),
                        update_btn.configure(state="normal"),
                    ))
                    _state["running"] = False

            threading.Thread(target=_run, daemon=True).start()

        def _show_done():
            for w in btn_row.winfo_children():
                w.destroy()
            tk.Button(
                btn_row, text="Close",
                command=root.destroy,
                bg=_GREEN, fg="white", relief="flat",
                font=("Segoe UI Bold", 10), padx=20, pady=6,
                cursor="hand2",
            ).pack()

        update_btn.configure(command=_do_update)

    def _check():
        info = check_for_update()
        root.after(0, lambda: _on_result(info))

    def _on_result(info):
        bar.stop()
        if info:
            _show_update(info)
        else:
            _show_up_to_date()

    threading.Thread(target=_check, daemon=True).start()
    root.mainloop()

if __name__ == "__main__":
    _run_standalone()