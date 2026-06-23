"""
HistoryTab — operation history that persists across sessions.

Uses PersistentHistory (utils/history.py) to survive app restarts.
The tab loads past entries on construction and appends new ones in real time.
"""
from datetime import datetime

import customtkinter as ctk

from gui.widgets import COLORS, ReusableWidgets, inter, mono
from utils.history import PersistentHistory


class HistoryTab(ctk.CTkFrame):
    ICONS = {
        "encode": "\U0001f512",
        "decode": "\U0001f513",
        "send":   "\u2709",
        "vault":  "\U0001f5c3",
        "shield": "\U0001f6e1",
    }

    def __init__(self, parent):
        super().__init__(parent, fg_color=COLORS["background"])
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._rendered_count = 0
        self._empty_label = None

        self._build_header()
        self._build_list()
        self._load_persisted()

    # ── Build ──────────────────────────────────────────────────────────────

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(10, 8))
        header.grid_columnconfigure(0, weight=1)

        ReusableWidgets.label(header, "SESSION & HISTORY", size=14, weight="bold").grid(
            row=0, column=0, sticky="w"
        )
        count = PersistentHistory.count()
        self._count_label = ReusableWidgets.label(
            header,
            f"{count} record{'s' if count != 1 else ''} stored",
            size=11,
            muted=True,
        )
        self._count_label.grid(row=1, column=0, sticky="w")

        ReusableWidgets.ghost_button(
            header, "Clear all", self._clear_all, width=110
        ).grid(row=0, column=1, sticky="e")

    def _build_list(self):
        self.list_frame = ctk.CTkScrollableFrame(
            self,
            fg_color=COLORS["background"],
            scrollbar_button_color=COLORS["card"],
            scrollbar_button_hover_color=COLORS["border"],
        )
        self.list_frame.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))
        self.list_frame.grid_columnconfigure(0, weight=1)

    # ── Load persisted entries on startup ─────────────────────────────────

    def _load_persisted(self):
        entries = PersistentHistory.all()
        if not entries:
            self._show_empty()
            return
        for entry in entries:
            self._render_entry_dict(entry)

    # ── Public API (called by other tabs) ──────────────────────────────────

    def add_entry(
        self,
        op_type: str,
        description: str,
        success: bool,
        duration_ms: float,
        reason: str = "",
    ) -> None:
        """Append a new entry, persist it, and render it."""
        PersistentHistory.add(op_type, description, success, duration_ms, reason)
        self._update_count_label()

        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "op_type": op_type,
            "description": description,
            "success": success,
            "duration_ms": duration_ms,
            "reason": reason,
        }
        if self._empty_label and self._empty_label.winfo_exists():
            self._empty_label.destroy()
            self._empty_label = None

        self._render_entry_dict(entry)
        self.after(80, self._scroll_to_latest)

    # ── Render ─────────────────────────────────────────────────────────────

    def _render_entry_dict(self, entry: dict) -> None:
        index = self._rendered_count
        self._rendered_count += 1

        card = ReusableWidgets.card(
            self.list_frame,
            border_width=1,
            border_color=COLORS["border"],
        )
        card.grid(row=index, column=0, sticky="ew", pady=(0, 10))
        card.grid_columnconfigure(1, weight=1)

        icon = self.ICONS.get(entry.get("op_type", ""), "\u2022")
        ctk.CTkLabel(
            card,
            text=icon,
            text_color=COLORS["accent"],
            font=inter(22, "bold"),
            width=42,
        ).grid(row=0, column=0, rowspan=3, padx=(14, 8), pady=12, sticky="n")

        # Timestamp — reformat ISO to HH:MM:SS if full ISO string
        ts = entry.get("timestamp", "")
        if "T" in ts:
            ts = ts.split("T")[-1]

        ctk.CTkLabel(
            card,
            text=ts,
            text_color=COLORS["text_muted"],
            font=mono(11),
        ).grid(row=0, column=1, sticky="w", padx=(0, 12), pady=(12, 0))

        ReusableWidgets.label(card, entry.get("description", ""), size=13).grid(
            row=1, column=1, sticky="w", padx=(0, 12), pady=(2, 2)
        )

        success = entry.get("success", False)
        reason = entry.get("reason", "")
        duration_ms = entry.get("duration_ms", 0)
        result_text = "\u2713 Success" if success else "\u2717 Failed"
        if not success and reason:
            result_text = f"{result_text}: {reason}"
        result_color = COLORS["accent"] if success else COLORS["error"]
        ctk.CTkLabel(
            card,
            text=f"{result_text} \u00b7 {float(duration_ms):.0f} ms",
            text_color=result_color,
            font=inter(12, "bold"),
        ).grid(row=2, column=1, sticky="w", padx=(0, 12), pady=(0, 12))

    def _show_empty(self):
        self._empty_label = ReusableWidgets.label(
            self.list_frame,
            "No operations yet — encode or decode something to see history.",
            muted=True,
        )
        self._empty_label.grid(row=0, column=0, sticky="w", padx=4, pady=10)

    def _clear_all(self):
        PersistentHistory.clear()
        self._rendered_count = 0
        for child in self.list_frame.winfo_children():
            child.destroy()
        self._show_empty()
        self._update_count_label()

    def _update_count_label(self):
        count = PersistentHistory.count()
        self._count_label.configure(
            text=f"{count} record{'s' if count != 1 else ''} stored"
        )

    def _scroll_to_latest(self):
        canvas = getattr(self.list_frame, "_parent_canvas", None)
        if canvas is not None:
            canvas.yview_moveto(1.0)
