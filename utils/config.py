import json
from copy import deepcopy
from pathlib import Path
from typing import Any


class Config:
    CONFIG_DIR = Path.home() / ".stegoxpress"
    CONFIG_PATH = CONFIG_DIR / "config.json"
    DEFAULTS = {
        "last_output_dir": str(Path.home()),
        "default_provider": "gmail",
        "window_width": 1000,
        "window_height": 680,
        "remember_sender_email": False,
        "sender_email": "",
        "theme": "dark",
    }
    _settings = None

    @classmethod
    def get(cls, key: str) -> Any:
        cls._ensure_loaded()
        return cls._settings.get(key, cls.DEFAULTS.get(key))

    @classmethod
    def set(cls, key: str, value: Any) -> None:
        cls._ensure_loaded()
        cls._settings[key] = value

        if key == "remember_sender_email" and not value:
            cls._settings["sender_email"] = ""

        cls._save()

    @classmethod
    def reset(cls) -> None:
        cls._settings = deepcopy(cls.DEFAULTS)
        cls._save()

    @classmethod
    def as_dict(cls) -> dict:
        cls._ensure_loaded()
        return deepcopy(cls._settings)

    @classmethod
    def _ensure_loaded(cls) -> None:
        if cls._settings is not None:
            return

        settings = deepcopy(cls.DEFAULTS)
        try:
            if cls.CONFIG_PATH.exists():
                with open(cls.CONFIG_PATH, "r", encoding="utf-8") as config_file:
                    loaded = json.load(config_file)
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
        cls.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        settings = deepcopy(cls._settings)

        if not settings.get("remember_sender_email", False):
            settings["sender_email"] = ""

        with open(cls.CONFIG_PATH, "w", encoding="utf-8") as config_file:
            json.dump(settings, config_file, indent=2)
