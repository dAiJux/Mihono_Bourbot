import argparse
import os
import sys
from pathlib import Path

def _bootstrap_libs():
    if getattr(sys, "frozen", False):
        root = Path(sys.executable).parent
    else:
        root = Path(os.path.dirname(os.path.abspath(__file__))).parent
    libs = root / "libs"
    if libs.exists():
        s = str(libs)
        if s not in sys.path:
            sys.path.insert(0, s)
        pysys32 = libs / "pywin32_system32"
        if pysys32.exists():
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(str(pysys32))
                except Exception:
                    pass
            os.environ["PATH"] = (
                str(pysys32) + os.pathsep + os.environ.get("PATH", "")
            )

_bootstrap_libs()

if getattr(sys, "frozen", False):
    _PROJECT_ROOT = str(Path(sys.executable).parent)
else:
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_PROJECT_ROOT)

def main():
    parser = argparse.ArgumentParser(
        description="Mihono Bourbot -- Umamusume Pretty Derby Bot",
    )
    parser.add_argument("--cli", action="store_true", help="Run without GUI")
    parser.add_argument("--runs", type=int, default=1, help="Number of runs (default: 1)")
    parser.add_argument("--test", action="store_true", help="Vision test mode")
    parser.add_argument("--config", type=str, default=os.path.join("config", "config.json"), help="Config path")
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