# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for StegoXpress v2.
# Build:  pyinstaller StegoXpress.spec
# Note: distribute binaries with a code-signing certificate where possible
# (see SECURITY.md / audit item: signed releases).

import sys
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# customtkinter and tkinterdnd2 ship data files (themes, tkdnd binaries)
datas = collect_data_files("customtkinter") + collect_data_files("tkinterdnd2")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "PIL._tkinter_finder",
        "tkinterdnd2",
        "customtkinter",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="StegoXpress",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX-packed binaries trigger antivirus false positives
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
