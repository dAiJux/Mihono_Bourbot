import argparse
import os
import sys
from pathlib import Path

_dll_handles = []

def _bootstrap_libs():
    if getattr(sys, "frozen", False):
        root = Path(sys.executable).parent
    else:
        root = Path(os.path.dirname(os.path.abspath(__file__))).parent
    libs = root / "libs"
    if not libs.exists():
        return
    for s in [str(libs), str(libs / "win32"), str(libs / "win32com"), str(libs / "win32comext")]:
        if os.path.isdir(s) and s not in sys.path:
            sys.path.insert(0, s)
    dll_dirs = set()
    for f in libs.rglob("*.pyd"):
        dll_dirs.add(f.parent)
    for f in libs.rglob("*.dll"):
        dll_dirs.add(f.parent)
    for d in dll_dirs:
        try:
            if hasattr(os, "add_dll_directory"):
                _dll_handles.append(os.add_dll_directory(str(d)))
            os.environ["PATH"] = str(d) + os.pathsep + os.environ.get("PATH", "")
        except Exception:
            pass

_bootstrap_libs()

if getattr(sys, "frozen", False):
    _PROJECT_ROOT = str(Path(sys.executable).parent)
else:
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_PROJECT_ROOT)

def main():
    parser = argparse.ArgumentParser(description="Mihono Bourbot -- Umamusume Pretty Derby Bot")
    parser.add_argument("--cli", action="store_true")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--config", type=str, default=os.path.join("config", "config.json"))
    args = parser.parse_args()

    Path("logs").mkdir(exist_ok=True)
    Path("templates").mkdir(exist_ok=True)
    Path("config").mkdir(exist_ok=True)

    if args.cli:
        from scripts.bot import MihonoBourbot
        bot = MihonoBourbot(config_path=args.config)
        if args.test:
            bot.test_vision()
        else:
            bot.run(num_runs=args.runs)
    else:
        from scripts.gui.launcher import main as gui_main
        gui_main()

if __name__ == "__main__":
    main()