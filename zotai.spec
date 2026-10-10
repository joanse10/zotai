# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Zotai: onedir build in dist/Zotai/."""

from PyInstaller.utils.hooks import collect_all

block_cipher = None

datas = [
    ("assets", "assets"),
    ("bin/tessdata", "bin/tessdata"),
    ("locales", "locales"),
]
binaries = []
hiddenimports = [
    "winrt.windows.ui.notifications",
    "winrt.windows.data.xml.dom",
    "winrt.windows.foundation",
    "winsdk.windows.ui.notifications",
    "winsdk.windows.data.xml.dom",
]

for pkg in ("customtkinter", "tkinterdnd2", "windows_toasts", "docx"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "pandas", "numpy", "pytest"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Zotai",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon="assets/icon.ico",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="Zotai",
)
