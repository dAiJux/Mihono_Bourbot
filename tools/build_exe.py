import PyInstaller.__main__
import os
import shutil

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("Building Mihono Bourbot.exe ...")
print("This may take a few minutes.\n")

PyInstaller.__main__.run([
  "scripts/__main__.py",
  "--name=Mihono Bourbot",
  "--onedir",
  "--windowed",
  "--icon=assets/logo.ico",
  f"--add-data=assets{os.pathsep}assets",
  "--hidden-import=scripts",
  "--hidden-import=scripts.bot",
  "--hidden-import=scripts.models",
  "--hidden-import=scripts.vision",
  "--hidden-import=scripts.vision.capture",
  "--hidden-import=scripts.vision.detection",
  "--hidden-import=scripts.vision.ocr",
  "--hidden-import=scripts.vision.training",
  "--hidden-import=scripts.automation",
  "--hidden-import=scripts.automation.clicks",
  "--hidden-import=scripts.automation.race",
  "--hidden-import=scripts.automation.training",
  "--hidden-import=scripts.automation.events",
  "--hidden-import=scripts.automation.unity",
  "--hidden-import=scripts.automation.navigation",
  "--hidden-import=scripts.decision",
  "--hidden-import=scripts.decision.engine",
  "--hidden-import=scripts.decision.events",
  "--hidden-import=scripts.gui",
  "--hidden-import=scripts.gui.config",
  "--hidden-import=scripts.gui.prereqs",
  "--hidden-import=scripts.gui.launcher",
  "--hidden-import=win32gui",
  "--hidden-import=win32ui",
  "--hidden-import=win32con",
  "--hidden-import=win32api",
  "--hidden-import=pywintypes",
  "--hidden-import=pytesseract",
  "--hidden-import=cv2",
  "--hidden-import=keyboard",
  "--hidden-import=numpy",
  "--noconfirm",
  "--clean",
])

dist_dir = os.path.join("dist", "Mihono Bourbot")

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

readme_path = os.path.join(dist_dir, "README.txt")
with open(readme_path, "w", encoding="utf-8") as f:
    f.write("""\
================================================================================
  Mihono Bourbot — Umamusume Pretty Derby Automation Bot
================================================================================

GETTING STARTED
---------------

  1. Install Tesseract OCR (required for reading in-game text):

     Option A — Automatic: launch the bot, it will offer to install it for you.

     Option B — Manual:
       - Download from: https://github.com/UB-Mannheim/tesseract/wiki
       - Run the installer and check "Add to PATH"
       - OR run in admin PowerShell: winget install UB-Mannheim.TesseractOCR

  2. Open your game in a visible window (emulator or DMM player).

  3. Double-click Mihono Bourbot.exe to launch the GUI.

  4. On first launch, the bot will ask you to capture templates.
     Templates are small screenshots of game UI buttons/icons that the bot
     uses to identify what is on screen.  Follow the on-screen instructions.

  5. Configure your preferences in the Settings tab, then click Start.

PREREQUISITES
-------------

  - Windows 10/11  (64-bit)
  - Tesseract OCR  (see step 1)
  - The game must be running in a visible window (not minimised)

FOLDER STRUCTURE
----------------

  Mihono Bourbot.exe   Main application (double-click to start)
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

  - "Tesseract not found": install Tesseract OCR (see step 1).
  - "No game window found": make sure the game is open and visible.
  - Templates not matching: re-capture templates via the GUI.
    The bot auto-adapts to different screen sizes, but if elements have
    changed (game update), templates need to be re-captured.
  - Bot clicks wrong spots: use the Calibrate tool in the GUI Settings tab.

  For more help, see the project documentation or open an issue.

================================================================================
""")

print("\n" + "=" * 60)
print("BUILD COMPLETE!")
print("=" * 60)
print(f"\nOutput folder: {os.path.abspath(dist_dir)}")
print("\nContents:")
print("  Mihono Bourbot.exe   <- Double-click to launch")
print("  config/            <- Configuration & event database")
print("  templates/         <- Your template images")
print("  logs/              <- Debug screenshots & logs")
print("  README.txt         <- How to get started")
print("\nYou can move/copy the entire Mihono Bourbot folder anywhere.")

