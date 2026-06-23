import json
from copy import deepcopy
from pathlib import Path
from typing import Any


class Config:
    CONFIG_DIR = Path.home() / ".stegoxpress"
    CONFIG_PATH = CONFIG_DIR / "config.json"
    DEFAULTS: dict[str, Any] = {
        "last_output_dir": str(Path.home()),
        "default_provider": "gmail",
        "window_width": 1000,
        "window_height": 680,
        "remember_sender_email": False,
        "sender_email": "",
        "theme": "dark",
    }
    _settings: dict[str, Any] | None = None

    # ── Private helper — always returns a non-None dict ────────────────────

    @classmethod
    def _loaded(cls) -> dict[str, Any]:
        """Ensure settings are loaded and return them (never None)."""
        if cls._settings is None:
            cls._ensure_loaded()
        if cls._settings is None:          # pragma: no cover — _ensure_loaded guarantees this
            cls._settings = deepcopy(cls.DEFAULTS)
        return cls._settings

    # ── Public API ──────────────────────────────────────────────────────────

    @classmethod
    def get(cls, key: str) -> Any:
        return cls._loaded().get(key, cls.DEFAULTS.get(key))

    @classmethod
    def set(cls, key: str, value: Any) -> None:
        s = cls._loaded()
        s[key] = value
        if key == "remember_sender_email" and not value:
            s["sender_email"] = ""
        cls._save()

    @classmethod
    def reset(cls) -> None:
        cls._settings = deepcopy(cls.DEFAULTS)
        cls._save()

    @classmethod
    def as_dict(cls) -> dict[str, Any]:
        return deepcopy(cls._loaded())

    # ── Internal ────────────────────────────────────────────────────────────

    @classmethod
    def _ensure_loaded(cls) -> None:
        if cls._settings is not None:
            return
        settings: dict[str, Any] = deepcopy(cls.DEFAULTS)
        try:
            if cls.CONFIG_PATH.exists():
                with open(cls.CONFIG_PATH, encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    settings.update(loaded)
        except (OSError, json.JSONDecodeError):
            settings = deepcopy(cls.DEFAULTS)
        if not settings.get("remember_sender_email", False):
            settings["sender_email"] = ""
        cls._settings = settings
        cls._save()

    @classmethod
    def _save(cls) -> None:
        settings = cls._loaded()
        try:
            cls.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            out: dict[str, Any] = deepcopy(settings)
            if not out.get("remember_sender_email", False):
                out["sender_email"] = ""
            with open(cls.CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(out, f, indent=2)
        except OSError:
            pass
