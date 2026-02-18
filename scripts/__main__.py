import sys
import os
from pathlib import Path

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_PROJECT_ROOT)

import argparse

def main():
    parser = argparse.ArgumentParser(
        description="Mihono Bourbot — Umamusume Pretty Derby Bot",
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
        from scripts import MihonoBourbot

        bot = MihonoBourbot(config_path=args.config)
        if args.test:
            bot.test_vision()
        else:
            bot.run(num_runs=args.runs)
    else:
        from scripts.gui import main as gui_main

        gui_main()

if __name__ == "__main__":
    main()
