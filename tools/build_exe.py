import PyInstaller.__main__
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

print("Building Mihono Bourbot.exe ...")
print("Heavy dependencies will be downloaded at first launch (not bundled).")
print("This may take a few minutes.\n")

ICO = os.path.join(ROOT, "assets", "logo.ico")
PYTHON_EXE = sys.executable

PyInstaller.__main__.run([
    "scripts/__main__.py",
    "--name=Mihono Bourbot",
    "--onedir",
    "--windowed",
    f"--icon={ICO}",
    f"--add-data=assets{os.pathsep}assets",
    "--hidden-import=scripts",
    "--hidden-import=scripts.gui",
    "--hidden-import=scripts.gui.config",
    "--hidden-import=scripts.gui.prereqs",
    "--hidden-import=scripts.gui.launcher",
    "--hidden-import=scripts.gui.debug_pip",
    "--collect-all=pip",
    "--copy-metadata=pip",
    "--exclude-module=cv2",
    "--exclude-module=numpy",
    "--exclude-module=easyocr",
    "--exclude-module=torch",
    "--exclude-module=torchvision",
    "--exclude-module=torchaudio",
    "--exclude-module=rapidfuzz",
    "--exclude-module=keyboard",
    "--exclude-module=win32gui",
    "--exclude-module=win32ui",
    "--exclude-module=win32con",
    "--exclude-module=win32api",
    "--exclude-module=pywintypes",
    "--exclude-module=scipy",
    "--exclude-module=skimage",
    "--exclude-module=matplotlib",
    "--exclude-module=pandas",
    "--noconfirm",
    "--clean",
])

dist_dir = os.path.join("dist", "Mihono Bourbot")

spec_file = "Mihono Bourbot.spec"
if os.path.exists(spec_file):
    os.remove(spec_file)
for item in ["config", "templates", "assets"]:
    src = item
    dst = os.path.join(dist_dir, item)
    if os.path.isdir(src):
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    elif os.path.isfile(src):
        shutil.copy2(src, dst)

os.makedirs(os.path.join(dist_dir, "logs", "debug"), exist_ok=True)
os.makedirs(os.path.join(dist_dir, "libs"), exist_ok=True)

readme_path = os.path.join(dist_dir, "README.txt")
with open(readme_path, "w", encoding="utf-8") as f:
    f.write("""\
================================================================================
  Mihono Bourbot — Umamusume Pretty Derby Automation Bot
================================================================================

GETTING STARTED
---------------

  1. Double-click Mihono Bourbot.exe to launch.

  2. On first launch, a setup window will appear automatically.
     It will download and install all required components (~800 MB).
     An internet connection is required for this one-time setup only.

  3. Open your game in a visible window (emulator or DMM player).

  4. The bot will then ask you to capture templates.
     Templates are small screenshots of game UI buttons/icons that the bot
     uses to identify what is on screen. Follow the on-screen instructions.

  5. Configure your preferences in the Settings tab, then click Start.

PREREQUISITES
-------------

  - Windows 10/11 (64-bit)
  - Internet connection (first launch only, for component download)
  - The game must be running in a visible window (not minimised)
  - No Python installation required — everything is self-contained

FOLDER STRUCTURE
----------------

  Mihono Bourbot.exe   Main application (double-click to start)
  libs/          Downloaded components (populated on first launch)
  config/            Configuration files & event database
  templates/         Template images captured from your game
  logs/              Runtime logs & debug screenshots
  README.txt         This file

CONTROLS (while the bot is running)
-----------------------------------

  F9                 Pause / Resume the bot
  F10                Stop the bot

TROUBLESHOOTING
---------------

  - Components not downloading: check your internet connection and firewall.
  - "No game window found": make sure the game is open and visible.
  - Templates not matching: re-capture templates via the GUI.
  - Bot clicks wrong spots: use the Calibrate tool in the GUI Settings tab.
  - To force re-download of components: delete the libs/ folder and restart.

================================================================================
""")

print("\n" + "=" * 60)
print("BUILD COMPLETE!")
print("=" * 60)
print(f"\nOutput folder: {os.path.abspath(dist_dir)}")
print("\nContents:")
print("  Mihono Bourbot.exe   <- Double-click to launch (~50 MB)")
print("  libs/          <- Populated automatically on first launch")
print("  config/            <- Configuration & event database")
print("  templates/         <- Your template images")
print("  logs/              <- Debug screenshots & logs")
print("  README.txt         <- How to get started")
print("\nShare the entire 'Mihono Bourbot' folder (zip it first).")
print("Users do NOT need Python installed — setup runs automatically.")