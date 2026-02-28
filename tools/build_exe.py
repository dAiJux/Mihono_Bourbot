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
    "--collect-all=cv2",
    "--collect-all=numpy",
    "--collect-all=PIL",
    "--collect-all=win32",
    "--collect-all=win32com",
    "--collect-all=pywintypes",
    "--hidden-import=win32api",
    "--hidden-import=win32con",
    "--hidden-import=win32gui",
    "--hidden-import=win32ui",
    "--hidden-import=pywintypes",
    "--hidden-import=pickletools",
    "--hidden-import=zipimport",
    "--hidden-import=distutils",
    "--hidden-import=distutils.version",
    "--hidden-import=distutils.util",
    "--hidden-import=distutils.sysconfig",
    "--hidden-import=importlib.metadata",
    "--hidden-import=importlib.resources",
    "--hidden-import=importlib.abc",
    "--hidden-import=xml.etree.ElementTree",
    "--hidden-import=logging.handlers",
    "--hidden-import=ctypes.util",
    "--hidden-import=ctypes.wintypes",
    "--hidden-import=modulefinder",
    "--hidden-import=tokenize",
    "--hidden-import=token",
    "--hidden-import=py_compile",
    "--hidden-import=compileall",
    "--hidden-import=tabnanny",
    "--hidden-import=pdb",
    "--hidden-import=profile",
    "--hidden-import=pstats",
    "--hidden-import=timeit",
    "--hidden-import=cProfile",
    "--hidden-import=doctest",
    "--hidden-import=difflib",
    "--hidden-import=inspect",
    "--hidden-import=dis",
    "--hidden-import=ast",
    "--hidden-import=symtable",
    "--hidden-import=opcode",
    "--hidden-import=marshal",
    "--hidden-import=struct",
    "--hidden-import=shelve",
    "--hidden-import=dbm",
    "--hidden-import=dbm.dumb",
    "--hidden-import=dbm.gnu",
    "--hidden-import=dbm.ndbm",
    "--hidden-import=csv",
    "--hidden-import=configparser",
    "--hidden-import=netrc",
    "--hidden-import=pprint",
    "--hidden-import=reprlib",
    "--hidden-import=textwrap",
    "--hidden-import=readline",
    "--hidden-import=rlcompleter",
    "--hidden-import=code",
    "--hidden-import=codeop",
    "--hidden-import=zipfile",
    "--hidden-import=tarfile",
    "--hidden-import=gzip",
    "--hidden-import=bz2",
    "--hidden-import=lzma",
    "--hidden-import=zlib",
    "--hidden-import=fileinput",
    "--hidden-import=filecmp",
    "--hidden-import=tempfile",
    "--hidden-import=glob",
    "--hidden-import=fnmatch",
    "--hidden-import=shutil",
    "--hidden-import=pathlib",
    "--hidden-import=stat",
    "--hidden-import=os.path",
    "--hidden-import=hashlib",
    "--hidden-import=hmac",
    "--hidden-import=secrets",
    "--hidden-import=string",
    "--hidden-import=re",
    "--hidden-import=enum",
    "--hidden-import=dataclasses",
    "--hidden-import=types",
    "--hidden-import=typing",
    "--hidden-import=typing_extensions",
    "--hidden-import=abc",
    "--hidden-import=contextlib",
    "--hidden-import=functools",
    "--hidden-import=itertools",
    "--hidden-import=operator",
    "--hidden-import=copy",
    "--hidden-import=pprint",
    "--hidden-import=weakref",
    "--hidden-import=gc",
    "--hidden-import=traceback",
    "--hidden-import=warnings",
    "--hidden-import=errno",
    "--hidden-import=signal",
    "--hidden-import=threading",
    "--hidden-import=multiprocessing",
    "--hidden-import=multiprocessing.pool",
    "--hidden-import=multiprocessing.managers",
    "--hidden-import=concurrent.futures",
    "--hidden-import=subprocess",
    "--hidden-import=socket",
    "--hidden-import=ssl",
    "--hidden-import=select",
    "--hidden-import=socketserver",
    "--hidden-import=http",
    "--hidden-import=http.client",
    "--hidden-import=http.server",
    "--hidden-import=urllib",
    "--hidden-import=urllib.request",
    "--hidden-import=urllib.parse",
    "--hidden-import=urllib.error",
    "--hidden-import=json",
    "--hidden-import=html",
    "--hidden-import=html.parser",
    "--hidden-import=xml",
    "--hidden-import=xml.etree",
    "--hidden-import=xml.dom",
    "--hidden-import=xml.sax",
    "--hidden-import=gettext",
    "--hidden-import=locale",
    "--hidden-import=argparse",
    "--hidden-import=getopt",
    "--hidden-import=logging",
    "--hidden-import=logging.config",
    "--hidden-import=unittest.runner",
    "--hidden-import=unittest.loader",
    "--hidden-import=unittest.suite",
    "--hidden-import=unittest.case",
    "--hidden-import=unittest.result",
    "--hidden-import=fractions",
    "--hidden-import=decimal",
    "--hidden-import=statistics",
    "--hidden-import=math",
    "--hidden-import=cmath",
    "--hidden-import=random",
    "--hidden-import=array",
    "--hidden-import=queue",
    "--hidden-import=heapq",
    "--hidden-import=bisect",
    "--hidden-import=collections",
    "--hidden-import=collections.abc",
    "--hidden-import=io",
    "--hidden-import=time",
    "--hidden-import=datetime",
    "--hidden-import=calendar",
    "--hidden-import=sysconfig",
    "--hidden-import=platform",
    "--hidden-import=builtins",
    "--hidden-import=site",
    "--exclude-module=easyocr",
    "--exclude-module=torch",
    "--exclude-module=torchvision",
    "--exclude-module=torchaudio",
    "--exclude-module=rapidfuzz",
    "--exclude-module=keyboard",
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

VCRT_DLLS = [
    "msvcp140.dll",
    "msvcp140_1.dll",
    "msvcp140_2.dll",
    "vcruntime140.dll",
    "vcruntime140_1.dll",
    "vcomp140.dll",
    "concrt140.dll",
]
vcrt_dst = os.path.join(dist_bot, "libs", "vcredist")
os.makedirs(vcrt_dst, exist_ok=True)
search_dirs = [
    os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32"),
    os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "SysWOW64"),
]
copied_vcrt = []
for dll_name in VCRT_DLLS:
    for sd in search_dirs:
        src_dll = os.path.join(sd, dll_name)
        if os.path.exists(src_dll):
            shutil.copy2(src_dll, os.path.join(vcrt_dst, dll_name))
            copied_vcrt.append(dll_name)
            break
if copied_vcrt:
    print(f"[OK]   Bundled VC++ runtime DLLs: {', '.join(copied_vcrt)}")
else:
    print("[WARN] No VC++ runtime DLLs found — users may need to install VC++ 2022 redistributable.")

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