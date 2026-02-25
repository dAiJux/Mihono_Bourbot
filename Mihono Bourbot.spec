# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['scripts\\__main__.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets')],
    hiddenimports=['scripts', 'scripts.bot', 'scripts.models', 'scripts.vision', 'scripts.vision.capture', 'scripts.vision.detection', 'scripts.vision.ocr', 'scripts.vision.training', 'scripts.automation', 'scripts.automation.clicks', 'scripts.automation.race', 'scripts.automation.training', 'scripts.automation.events', 'scripts.automation.unity', 'scripts.automation.navigation', 'scripts.decision', 'scripts.decision.engine', 'scripts.decision.events', 'scripts.gui', 'scripts.gui.config', 'scripts.gui.prereqs', 'scripts.gui.launcher', 'win32gui', 'win32ui', 'win32con', 'win32api', 'pywintypes', 'easyocr', 'rapidfuzz', 'cv2', 'keyboard', 'numpy'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Mihono Bourbot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\logo.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Mihono Bourbot',
)
