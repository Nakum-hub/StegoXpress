from datetime import datetime

import customtkinter as ctk

from gui.widgets import COLORS, ReusableWidgets, inter, mono


class HistoryTab(ctk.CTkFrame):
    ICONS = {
        "encode": "🔒",
        "decode": "🔓",
        "send": "✉",
    }

    def __init__(self, parent):
        super().__init__(parent, fg_color=COLORS["background"])
        self.entries = []
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(10, 8))
        header.grid_columnconfigure(0, weight=1)

        ReusableWidgets.label(header, "SESSION HISTORY", size=14, weight="bold").grid(
            row=0,
            column=0,
            sticky="w",
        )
        self.clear_button = ReusableWidgets.ghost_button(
            header,
            "Clear",
            self.clear,
            width=110,
        )
        self.clear_button.grid(row=0, column=1, sticky="e")

        self.list_frame = ctk.CTkScrollableFrame(
            self,
            fg_color=COLORS["background"],
            scrollbar_button_color=COLORS["card"],
            scrollbar_button_hover_color=COLORS["border"],
        )
        self.list_frame.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))
        self.list_frame.grid_columnconfigure(0, weight=1)

        self.empty_label = ReusableWidgets.label(
            self.list_frame,
            "No operations in this session yet.",
            muted=True,
        )
        self.empty_label.grid(row=0, column=0, sticky="w", padx=4, pady=10)

    def add_entry(self, op_type, description, success, duration_ms, reason=""):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.entries.append(
            {
                "timestamp": timestamp,
                "op_type": op_type,
                "description": description,
                "success": success,
                "duration_ms": duration_ms,
                "reason": reason,
            }
        )
        self._render_entry(len(self.entries) - 1)
        self.after(80, self._scroll_to_latest)

    def clear(self):
        self.entries.clear()
        for child in self.list_frame.winfo_children():
            child.destroy()
        self.empty_label = ReusableWidgets.label(
            self.list_frame,
            "No operations in this session yet.",
            muted=True,
        )
        self.empty_label.grid(row=0, column=0, sticky="w", padx=4, pady=10)

    def _render_entry(self, index):
        if self.empty_label.winfo_exists():
            self.empty_label.destroy()

        entry = self.entries[index]
        card = ReusableWidgets.card(
            self.list_frame,
            border_width=1,
            border_color=COLORS["border"],
        )
        card.grid(row=index, column=0, sticky="ew", pady=(0, 10))
        card.grid_columnconfigure(1, weight=1)

        icon = self.ICONS.get(entry["op_type"], "•")
        ctk.CTkLabel(
            card,
            text=icon,
            text_color=COLORS["accent"],
            font=inter(22, "bold"),
            width=42,
        ).grid(row=0, column=0, rowspan=3, padx=(14, 8), pady=12, sticky="n")

        ctk.CTkLabel(
            card,
            text=entry["timestamp"],
            text_color=COLORS["text_muted"],
            font=mono(11),
        ).grid(row=0, column=1, sticky="w", padx=(0, 12), pady=(12, 0))

        ReusableWidgets.label(card, entry["description"], size=13).grid(
            row=1,
            column=1,
            sticky="w",
            padx=(0, 12),
            pady=(2, 2),
        )

        result_text = "✓ Success" if entry["success"] else "✗ Failed"
        if not entry["success"] and entry.get("reason"):
            result_text = f"{result_text}: {entry['reason']}"
        result_color = COLORS["accent"] if entry["success"] else COLORS["error"]
        ctk.CTkLabel(
            card,
            text=f"{result_text} · {entry['duration_ms']:.0f} ms",
            text_color=result_color,
            font=inter(12, "bold"),
        ).grid(row=2, column=1, sticky="w", padx=(0, 12), pady=(0, 12))

    def _scroll_to_latest(self):
        canvas = getattr(self.list_frame, "_parent_canvas", None)
        if canvas is not None:
            canvas.yview_moveto(1.0)
