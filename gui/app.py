import customtkinter as ctk

from gui.decode_tab import DecodeTab
from gui.encode_tab import EncodeTab
from gui.send_tab import SendTab
from gui.widgets import COLORS, ReusableWidgets, inter


class StegoXpressApp:
    def __init__(self, root):
        self.root = root
        self.root.title("StegoXpress")
        self.root.geometry("1000x680")
        self.root.minsize(800, 600)
        self.root.resizable(True, True)
        self.root.configure(fg_color=COLORS["background"])
        ctk.set_appearance_mode("dark")

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
            text="StegoXpress",
            text_color=COLORS["accent"],
            font=inter(20, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            brand_block,
            text="Secure hidden communication",
            text_color=COLORS["text_muted"],
            font=inter(11),
        ).grid(row=1, column=0, sticky="w")

        about = ReusableWidgets.ghost_button(top, "About", self.show_about, width=100)
        about.grid(row=0, column=1, sticky="e", padx=22, pady=14)

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

        encode_host = self.tabs.tab("↑  ENCODE")
        decode_host = self.tabs.tab("↓  DECODE")
        send_host = self.tabs.tab("✉  SEND")
        encode_host.grid_columnconfigure(0, weight=1)
        encode_host.grid_rowconfigure(0, weight=1)
        decode_host.grid_columnconfigure(0, weight=1)
        decode_host.grid_rowconfigure(0, weight=1)
        send_host.grid_columnconfigure(0, weight=1)
        send_host.grid_rowconfigure(0, weight=1)

        self.encode_tab = EncodeTab(encode_host, self.on_encode_complete)
        self.encode_tab.grid(row=0, column=0, sticky="nsew")
        self.encode_tab.status_callback = self.set_status

        self.decode_tab = DecodeTab(decode_host)
        self.decode_tab.grid(row=0, column=0, sticky="nsew")
        self.decode_tab.status_callback = self.set_status

        self.send_tab = SendTab(send_host, self.on_send_success)
        self.send_tab.grid(row=0, column=0, sticky="nsew")
        self.send_tab.status_callback = self.set_status

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
                "Hide encrypted text or files inside PNG-safe images.\n\n"
                "Encryption uses password-derived AES-256-GCM keys. "
                "Payloads are stored with length-prefixed LSB encoding."
            ),
            text_color=COLORS["text_muted"],
            font=inter(12),
            justify="left",
            wraplength=340,
        ).pack(anchor="w", padx=20, pady=(0, 18))
        ReusableWidgets.primary_button(card, "Close", dialog.destroy, width=120).pack(anchor="e", padx=20, pady=(0, 20))

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
