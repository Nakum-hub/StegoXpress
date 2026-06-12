import customtkinter as ctk
from tkinter import filedialog
import tkinter as tk

from gui.decode_tab import DecodeTab
from gui.encode_tab import EncodeTab
from gui.history_tab import HistoryTab
from gui.send_tab import SendTab
from gui.shield_tab import ShieldTab
from gui.vault_tab import VaultTab
from gui.widgets import COLORS, ReusableWidgets, inter
from utils.config import Config
from utils.logger import StegoLogger


class StegoXpressApp:
    def __init__(self, root):
        self.logger = StegoLogger.get()
        self.root = root
        self.root.title("StegoXpress")
        self.root.geometry(f"{Config.get('window_width')}x{Config.get('window_height')}")
        self.root.minsize(800, 600)
        self.root.resizable(True, True)
        self.root.configure(fg_color=COLORS["background"])
        ctk.set_appearance_mode(Config.get("theme"))
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

        self._build_top_bar()
        self._build_tabs()
        self._build_status_bar()

    def _build_top_bar(self):
        top = ctk.CTkFrame(self.root, fg_color=COLORS["surface"], corner_radius=0)
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(0, weight=1)

        brand_block = ctk.CTkFrame(top, fg_color="transparent")
        brand_block.grid(row=0, column=0, sticky="w", padx=22, pady=14)

        ctk.CTkLabel(
            brand_block,
            text="StegoXpress ◈",
            text_color=COLORS["accent"],
            font=inter(20, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            brand_block,
            text="Secure hidden communication",
            text_color=COLORS["text_muted"],
            font=inter(11),
        ).grid(row=1, column=0, sticky="w")

        settings = ReusableWidgets.ghost_button(top, "⚙", self.show_settings, width=54)
        settings.grid(row=0, column=1, sticky="e", padx=(0, 10), pady=14)

        about = ReusableWidgets.ghost_button(top, "About", self.show_about, width=100)
        about.grid(row=0, column=2, sticky="e", padx=(0, 22), pady=14)

    def _build_tabs(self):
        self.tabs = ctk.CTkTabview(
            self.root,
            fg_color=COLORS["background"],
            segmented_button_fg_color=COLORS["surface"],
            segmented_button_selected_color=COLORS["accent"],
            segmented_button_selected_hover_color=COLORS["accent_dim"],
            segmented_button_unselected_color=COLORS["surface"],
            segmented_button_unselected_hover_color=COLORS["card"],
            text_color=COLORS["text_primary"],
            corner_radius=10,
            border_width=0,
        )
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=18, pady=16)
        self.tabs.add("↑  ENCODE")
        self.tabs.add("↓  DECODE")
        self.tabs.add("✉  SEND")
        self.tabs.add("🔐  VAULT")
        self.tabs.add("🛡  SHIELD")
        self.tabs.add("⚙  HISTORY")

        encode_host  = self.tabs.tab("↑  ENCODE")
        decode_host  = self.tabs.tab("↓  DECODE")
        send_host    = self.tabs.tab("✉  SEND")
        vault_host   = self.tabs.tab("🔐  VAULT")
        shield_host  = self.tabs.tab("🛡  SHIELD")
        history_host = self.tabs.tab("⚙  HISTORY")

        for host in (encode_host, decode_host, send_host,
                     vault_host, shield_host, history_host):
            host.grid_columnconfigure(0, weight=1)
            host.grid_rowconfigure(0, weight=1)

        self.encode_tab = EncodeTab(encode_host, self.on_encode_complete)
        self.encode_tab.grid(row=0, column=0, sticky="nsew")
        self.encode_tab.status_callback = self.set_status
        self.encode_tab.history_callback = self.add_history

        self.decode_tab = DecodeTab(decode_host)
        self.decode_tab.grid(row=0, column=0, sticky="nsew")
        self.decode_tab.status_callback = self.set_status
        self.decode_tab.history_callback = self.add_history

        self.send_tab = SendTab(send_host, self.on_send_success)
        self.send_tab.grid(row=0, column=0, sticky="nsew")
        self.send_tab.status_callback = self.set_status
        self.send_tab.history_callback = self.add_history

        self.vault_tab = VaultTab(
            vault_host,
            status_callback=self.set_status,
            history_callback=self.add_history,
        )
        self.vault_tab.grid(row=0, column=0, sticky="nsew")

        self.shield_tab = ShieldTab(
            shield_host,
            status_callback=self.set_status,
            history_callback=self.add_history,
        )
        self.shield_tab.grid(row=0, column=0, sticky="nsew")

        self.history_tab = HistoryTab(history_host)
        self.history_tab.grid(row=0, column=0, sticky="nsew")

    def _build_status_bar(self):
        status = ctk.CTkFrame(self.root, fg_color=COLORS["surface"], corner_radius=0, height=30)
        status.grid(row=2, column=0, sticky="ew")
        status.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            status,
            text="v2.0.0",
            text_color=COLORS["text_muted"],
            font=inter(11),
        ).grid(row=0, column=0, sticky="w", padx=18, pady=6)

        self.status_value = ctk.CTkLabel(
            status,
            text="Ready",
            text_color=COLORS["text_muted"],
            font=inter(11),
        )
        self.status_value.grid(row=0, column=2, sticky="e", padx=18, pady=6)

    def set_status(self, message):
        self.status_value.configure(text=message)

    def on_encode_complete(self, output_path):
        self.decode_tab.load_image_path(output_path)
        self.send_tab.set_image_path(output_path)
        self.tabs.set("↓  DECODE")
        self.show_toast(f"Encoded image ready: {output_path}")

    def on_send_success(self, recipient):
        self.show_toast(f"Image sent to {recipient}")

    def add_history(self, op_type, description, success, duration_ms, reason=""):
        self.history_tab.add_entry(op_type, description, success, duration_ms, reason)

    def show_about(self):
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("About StegoXpress")
        dialog.geometry("420x260")
        dialog.configure(fg_color=COLORS["background"])
        dialog.transient(self.root)
        dialog.grab_set()

        card = ReusableWidgets.card(dialog, border_width=1, border_color=COLORS["border"])
        card.pack(fill="both", expand=True, padx=18, pady=18)
        ReusableWidgets.label(card, "StegoXpress", size=22, weight="bold").pack(anchor="w", padx=20, pady=(20, 4))
        ctk.CTkLabel(
            card,
            text=(
                "Hide encrypted secrets in images, audio, and PNG metadata.\n\n"
                "Features: dual-password vault, N-of-K secret sharing, "
                "tamper-proof seal, self-destruct, adaptive LSB, "
                "entropy heatmap, and steganalysis scoring."
            ),
            text_color=COLORS["text_muted"],
            font=inter(12),
            justify="left",
            wraplength=340,
        ).pack(anchor="w", padx=20, pady=(0, 18))
        ReusableWidgets.primary_button(card, "Close", dialog.destroy, width=120).pack(anchor="e", padx=20, pady=(0, 20))

    def show_settings(self):
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Settings")
        dialog.geometry("560x460")
        dialog.configure(fg_color=COLORS["background"])
        dialog.transient(self.root)
        dialog.grab_set()

        card = ReusableWidgets.card(dialog, border_width=1, border_color=COLORS["border"])
        card.pack(fill="both", expand=True, padx=18, pady=18)
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, weight=0)

        ReusableWidgets.label(card, "SETTINGS", size=16, weight="bold").grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="w",
            padx=20,
            pady=(18, 14),
        )

        ReusableWidgets.label(card, "Default output directory", muted=True).grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="w",
            padx=20,
        )
        output_entry = ReusableWidgets.entry(card, "Default output directory", width=360)
        output_entry.grid(row=2, column=0, sticky="ew", padx=(20, 10), pady=(6, 14))
        output_entry.insert(0, Config.get("last_output_dir"))

        def browse_output_dir():
            directory = filedialog.askdirectory(initialdir=output_entry.get() or Config.get("last_output_dir"))
            if directory:
                output_entry.delete(0, "end")
                output_entry.insert(0, directory)

        ReusableWidgets.ghost_button(card, "Browse", browse_output_dir, width=110).grid(
            row=2,
            column=1,
            sticky="e",
            padx=(0, 20),
            pady=(6, 14),
        )

        ReusableWidgets.label(card, "Default email provider", muted=True).grid(
            row=3,
            column=0,
            columnspan=2,
            sticky="w",
            padx=20,
        )
        provider_selector = ctk.CTkSegmentedButton(
            card,
            values=["Gmail", "Outlook", "Yahoo", "Custom"],
            selected_color=COLORS["accent"],
            selected_hover_color=COLORS["accent_dim"],
            unselected_color=COLORS["surface"],
            unselected_hover_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            font=inter(12, "bold"),
            corner_radius=8,
        )
        provider_selector.grid(row=4, column=0, columnspan=2, sticky="ew", padx=20, pady=(6, 14))
        provider_selector.set(Config.get("default_provider").title())

        remember_var = tk.BooleanVar(value=bool(Config.get("remember_sender_email")))
        remember_check = ctk.CTkCheckBox(
            card,
            text="Remember sender email",
            variable=remember_var,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_dim"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            font=inter(12),
        )
        remember_check.grid(row=5, column=0, columnspan=2, sticky="w", padx=20, pady=(0, 12))

        ReusableWidgets.label(card, "Theme", muted=True).grid(
            row=6,
            column=0,
            columnspan=2,
            sticky="w",
            padx=20,
        )
        theme_selector = ctk.CTkSegmentedButton(
            card,
            values=["Dark", "Light", "System"],
            selected_color=COLORS["accent"],
            selected_hover_color=COLORS["accent_dim"],
            unselected_color=COLORS["surface"],
            unselected_hover_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            font=inter(12, "bold"),
            corner_radius=8,
        )
        theme_selector.grid(row=7, column=0, columnspan=2, sticky="ew", padx=20, pady=(6, 20))
        theme_selector.set(Config.get("theme").title())

        button_row = ctk.CTkFrame(card, fg_color="transparent")
        button_row.grid(row=8, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 18))
        button_row.grid_columnconfigure(0, weight=1)

        def reset_settings():
            Config.reset()
            output_entry.delete(0, "end")
            output_entry.insert(0, Config.get("last_output_dir"))
            provider_selector.set(Config.get("default_provider").title())
            remember_var.set(Config.get("remember_sender_email"))
            theme_selector.set(Config.get("theme").title())
            self.send_tab.apply_config_defaults()
            ctk.set_appearance_mode(Config.get("theme"))

        def save_settings():
            Config.set("last_output_dir", output_entry.get().strip() or Config.DEFAULTS["last_output_dir"])
            Config.set("default_provider", provider_selector.get().lower())
            Config.set("remember_sender_email", bool(remember_var.get()))
            if Config.get("remember_sender_email"):
                Config.set("sender_email", self.send_tab.sender_entry.get().strip())
            Config.set("theme", theme_selector.get().lower())
            ctk.set_appearance_mode(Config.get("theme"))
            self.send_tab.apply_config_defaults()
            dialog.destroy()

        ReusableWidgets.ghost_button(button_row, "Reset to defaults", reset_settings, width=170).grid(
            row=0,
            column=0,
            sticky="w",
        )
        ReusableWidgets.primary_button(button_row, "Save", save_settings, width=120).grid(
            row=0,
            column=1,
            sticky="e",
        )

    def show_toast(self, message):
        toast = ctk.CTkToplevel(self.root)
        toast.overrideredirect(True)
        toast.configure(fg_color=COLORS["card"])

        label = ctk.CTkLabel(
            toast,
            text=message,
            text_color=COLORS["text_primary"],
            font=inter(12, "bold"),
            padx=18,
            pady=12,
            wraplength=420,
        )
        label.pack()

        self.root.update_idletasks()
        root_x = self.root.winfo_rootx()
        root_y = self.root.winfo_rooty()
        root_w = self.root.winfo_width()
        toast_w = 460
        toast_h = 58
        toast.geometry(f"{toast_w}x{toast_h}+{root_x + root_w - toast_w - 28}+{root_y + 78}")
        toast.after(3000, toast.destroy)

    def on_close(self):
        Config.set("window_width", self.root.winfo_width())
        Config.set("window_height", self.root.winfo_height())
        self.root.destroy()
