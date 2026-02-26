import os
import shutil
import secrets
import sys
from pathlib import Path

import PyInstaller.__main__

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_ROOT)

print("Building Mihono Bourbot...")
print("Heavy dependencies will be downloaded at first launch (not bundled).")
print("This may take a few minutes.\n")

TOKEN_FILE = "updater_token.txt"
TOKEN_DATA_FILE = "_token_data.py"

token_path = Path(TOKEN_FILE)
if not token_path.exists():
    print(f"[WARN] {TOKEN_FILE} not found — updater will work without auth (public releases only).")
    token_bytes = b""
else:
    token_bytes = token_path.read_text(encoding="utf-8").strip().encode("utf-8")
    print(f"[OK]   Token loaded ({len(token_bytes)} chars), embedding encrypted.")

key = secrets.token_bytes(len(token_bytes)) if token_bytes else b""
enc = bytes(b ^ k for b, k in zip(token_bytes, key))

with open(TOKEN_DATA_FILE, "w", encoding="utf-8") as f:
    f.write(f"_ENC = {list(enc)}\n")
    f.write(f"_KEY = {list(key)}\n")

print("[OK]   Token data written to temporary module.\n")

PyInstaller.__main__.run([
    os.path.join(_ROOT, "scripts", "__main__.py"),
    "--name=Mihono Bourbot",
    "--onedir",
    "--windowed",
    "--icon=assets/logo.ico",
    f"--add-data={os.path.join(_ROOT, 'assets')}{os.pathsep}assets",
    "--hidden-import=scripts",
    "--hidden-import=scripts.gui",
    "--hidden-import=scripts.gui.config",
    "--hidden-import=scripts.gui.prereqs",
    "--hidden-import=scripts.gui.launcher",
    "--hidden-import=updater",
    "--collect-all=pip",
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

print("\n[BUILD] Building Updater.exe ...\n")

PyInstaller.__main__.run([
    os.path.join(_ROOT, "updater.py"),
    "--name=Updater",
    "--onefile",
    "--windowed",
    "--icon=assets/logo.ico",
    "--hidden-import=_token_data",
    f"--add-data={os.path.join(_ROOT, TOKEN_DATA_FILE)}{os.pathsep}.",
    "--noconfirm",
    "--clean",
])

if Path(TOKEN_DATA_FILE).exists():
    os.remove(TOKEN_DATA_FILE)
    print("[OK]   Temporary token module deleted.")

dist_bot = os.path.join("dist", "Mihono Bourbot")
updater_exe = os.path.join("dist", "Updater.exe")

for item in ["config", "templates", "assets", "version.txt"]:
    src = item
    dst = os.path.join(dist_bot, item)
    if os.path.isdir(src):
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    elif os.path.isfile(src):
        shutil.copy2(src, dst)

if os.path.exists(updater_exe):
    shutil.copy2(updater_exe, os.path.join(dist_bot, "Updater.exe"))
    shutil.rmtree(os.path.join("dist", "Updater"), ignore_errors=True)
    os.remove(updater_exe)
    print("[OK]   Updater.exe moved to bot folder.")

os.makedirs(os.path.join(dist_bot, "logs", "debug"), exist_ok=True)
os.makedirs(os.path.join(dist_bot, "libs"), exist_ok=True)

for spec in ["Mihono Bourbot.spec", "Updater.spec"]:
    if os.path.exists(spec):
        os.remove(spec)

readme_path = os.path.join(dist_bot, "README.txt")
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
     Follow the on-screen instructions.

  5. Configure your preferences in the Settings tab, then click Start.

UPDATING
--------

  Run Updater.exe to check for and apply updates automatically.

FOLDER STRUCTURE
----------------

  Mihono Bourbot.exe   Main application
  Updater.exe          Update checker
  libs/              Downloaded components (populated on first launch)
  config/            Configuration files & event database
  templates/         Template images captured from your game
  logs/              Runtime logs & debug screenshots

CONTROLS (while the bot is running)
-----------------------------------

  F9                 Pause / Resume the bot
  F10                Stop the bot

TROUBLESHOOTING
---------------

  - Components not downloading: check your internet connection and firewall.
  - "No game window found": make sure the game is open and visible.
  - Templates not matching: re-capture templates via the GUI.
  - To force re-download of components: delete the libs/ folder and restart.

================================================================================
""")

print("\n" + "=" * 60)
print("BUILD COMPLETE!")
print("=" * 60)
print(f"\nOutput folder: {os.path.abspath(dist_bot)}")
print("\nContents:")
print("  Mihono Bourbot.exe   <- Main bot (~50 MB)")
print("  Updater.exe          <- Update checker")
print("  libs/              <- Populated on first launch")
print("  config/            <- Configuration")
print("  templates/         <- Game templates")
print("  README.txt")
print("\nThe token is compiled into Updater.exe — no external token file.")