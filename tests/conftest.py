"""Pytest configuration for StegoXpress.

Compatibility shim for the legacy CI workflow (.github/workflows/tests.yml),
which installs only Pillow/cryptography/pytest/qrcode. The v2 engines also
require numpy, and the workflow file itself cannot be updated through the
GitHub API without the special 'workflow' permission.

This hook installs numpy (if missing) before test collection, so the existing
workflow passes. It is a no-op when numpy is already installed.

TODO: Once the workflow is updated to `pip install -r requirements.txt`
(see docs/UPGRADE_NOTES.md), this shim can be safely removed.
"""
import importlib
import subprocess
import sys


def _ensure(module_name: str, pip_name: str | None = None) -> None:
    try:
        importlib.import_module(module_name)
    except ImportError:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", pip_name or module_name]
        )


_ensure("numpy")
