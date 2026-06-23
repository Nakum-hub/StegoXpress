"""
PersistentHistory — stores operation records across sessions.

Records are written to ~/.stegoxpress/history.json as a JSON array (newest
last).  A configurable cap (default 200) prevents unbounded growth.  No
sensitive data (passwords, plaintext payloads) is ever written.
"""
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any


class PersistentHistory:
    HISTORY_DIR = Path.home() / ".stegoxpress"
    HISTORY_PATH = HISTORY_DIR / "history.json"
    MAX_ENTRIES = 200

    _entries: list[dict] | None = None

    # ── Public API ──────────────────────────────────────────────────────────

    @classmethod
    def add(
        cls,
        op_type: str,
        description: str,
        success: bool,
        duration_ms: float,
        reason: str = "",
    ) -> None:
        """Append one operation record and persist immediately."""
        cls._ensure_loaded()
        entry = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "op_type": op_type,
            "description": description,
            "success": success,
            "duration_ms": round(duration_ms, 1),
            "reason": reason,
        }
        cls._entries.append(entry)  # type: ignore[union-attr]
        # Trim to cap
        if len(cls._entries) > cls.MAX_ENTRIES:  # type: ignore[arg-type]
            cls._entries = cls._entries[-cls.MAX_ENTRIES :]  # type: ignore[index]
        cls._save()

    @classmethod
    def all(cls) -> list[dict]:
        """Return all stored entries (oldest first), safe to mutate."""
        cls._ensure_loaded()
        return deepcopy(cls._entries)  # type: ignore[arg-type]

    @classmethod
    def clear(cls) -> None:
        """Delete all history entries and persist the empty state."""
        cls._entries = []
        cls._save()

    @classmethod
    def count(cls) -> int:
        cls._ensure_loaded()
        return len(cls._entries)  # type: ignore[arg-type]

    # ── Internal ────────────────────────────────────────────────────────────

    @classmethod
    def _ensure_loaded(cls) -> None:
        if cls._entries is not None:
            return
        cls._entries = []
        try:
            if cls.HISTORY_PATH.exists():
                raw = cls.HISTORY_PATH.read_text(encoding="utf-8")
                loaded = json.loads(raw)
                if isinstance(loaded, list):
                    cls._entries = loaded[-cls.MAX_ENTRIES :]
        except (OSError, json.JSONDecodeError):
            cls._entries = []

    @classmethod
    def _save(cls) -> None:
        try:
            cls.HISTORY_DIR.mkdir(parents=True, exist_ok=True)
            cls.HISTORY_PATH.write_text(
                json.dumps(cls._entries, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass  # History persistence failure is non-fatal
