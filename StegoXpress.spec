# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for StegoXpress v2.1
#
# Build:
#   pip install pyinstaller
#   pyinstaller StegoXpress.spec
#
# Output: dist/StegoXpress  (or dist/StegoXpress.exe on Windows)
#
# NOTE: distribute binaries with a code-signing certificate (see SECURITY.md).
# UPX is deliberately disabled — UPX-packed binaries trigger antivirus false positives.

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# ── Data files ──────────────────────────────────────────────────────────────
# customtkinter and tkinterdnd2 ship themes/tkdnd native binaries alongside
# their Python code. PyInstaller needs them included explicitly.
datas = (
    collect_data_files("customtkinter")
    + collect_data_files("tkinterdnd2")
)

# ── Hidden imports ───────────────────────────────────────────────────────────
# PyInstaller cannot trace dynamic imports in the cryptography package because
# hazmat backends are loaded at runtime.  List every submodule that StegoXpress
# uses so the bundle doesn't crash on decrypt() or encrypt() calls.
hidden = [
    # Pillow
    "PIL._tkinter_finder",
    "PIL.PngImagePlugin",
    "PIL.JpegImagePlugin",
    "PIL.Image",

    # tkinterdnd2 / customtkinter
    "tkinterdnd2",
    "customtkinter",

    # cryptography — AES-GCM
    "cryptography.hazmat.primitives.ciphers.aead",
    "cryptography.hazmat.primitives.ciphers.algorithms",
    "cryptography.hazmat.primitives.ciphers.modes",
    "cryptography.hazmat.backends.openssl.aead",

    # cryptography — KDF
    "cryptography.hazmat.primitives.kdf.pbkdf2",
    "cryptography.hazmat.primitives.kdf.hkdf",
    "cryptography.hazmat.primitives.kdf.scrypt",

    # cryptography — HMAC / hashes
    "cryptography.hazmat.primitives.hmac",
    "cryptography.hazmat.primitives.hashes",

    # cryptography — backend
    "cryptography.hazmat.backends",
    "cryptography.hazmat.backends.openssl",
    "cryptography.hazmat.backends.openssl.backend",
    "cryptography.hazmat.bindings.openssl.binding",

    # argon2-cffi (optional but bundled if present)
    "argon2",
    "argon2.low_level",
    "argon2._utils",
    "_argon2_cffi_bindings",

    # NumPy
    "numpy",
    "numpy.core._multiarray_umath",
    "numpy.core._multiarray_tests",

    # stdlib used at runtime
    "email.mime.multipart",
    "email.mime.base",
    "email.mime.text",
    "email.mime.image",
    "smtplib",
    "wave",
    "struct",
    "logging.handlers",
]

# Also pull in ALL cryptography submodules to be safe
hidden += collect_submodules("cryptography.hazmat.primitives")
hidden += collect_submodules("cryptography.hazmat.backends.openssl")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "test",
        "tests",
        "pytest",
        "mypy",
        "ruff",
        "pip",
        "setuptools",
        "distutils",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

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
    upx=False,           # UPX triggers AV false positives — keep disabled
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,       # GUI mode — no terminal window on Windows
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icon.ico" if sys.platform == "win32" else None,
    version_file=None,
)
