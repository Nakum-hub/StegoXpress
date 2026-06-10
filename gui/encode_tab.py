import os
import queue
import threading
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image

from core.crypto_engine import CryptoEngine
from core.file_packer import FilePacker
from core.lsb_engine import LSBEngine
from gui.widgets import COLORS, ReusableWidgets, format_bytes, inter, mono


class EncodeTab(ctk.CTkFrame):
    def __init__(self, parent, on_encode_complete: callable):
        super().__init__(parent, fg_color=COLORS["background"])
        self.on_encode_complete = on_encode_complete
        self.status_callback = None
        self.image_path = None
        self.cover_image = None
        self.selected_file = None
        self.ui_queue = queue.Queue()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.content = ctk.CTkScrollableFrame(
            self,
            fg_color=COLORS["background"],
            scrollbar_button_color=COLORS["card"],
            scrollbar_button_hover_color=COLORS["border"],
        )
        self.content.grid(row=0, column=0, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_columnconfigure(1, weight=1)

        self._build_left_column()
        self._build_right_column()
        self._build_action_row()
        self.after(100, self.process_ui_queue)

    def _build_left_column(self):
        left = ReusableWidgets.card(self.content)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12), pady=(0, 14))
        left.grid_columnconfigure(0, weight=1)

        self._section_header(left, "COVER IMAGE", 0)
        self.preview = ReusableWidgets.image_preview(left, size=280)
        self.preview.grid(row=1, column=0, pady=(10, 12))

        browse = ReusableWidgets.ghost_button(left, "Browse Image", self.browse_image)
        browse.grid(row=2, column=0, pady=(0, 14))

        self.capacity = ReusableWidgets.capacity_bar(left, width=360)
        self.capacity.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 12))

        self.image_info = ReusableWidgets.label(left, "No image selected", muted=True)
        self.image_info.grid(row=4, column=0, sticky="w", padx=20, pady=(0, 18))

    def _build_right_column(self):
        right = ReusableWidgets.card(self.content)
        right.grid(row=0, column=1, sticky="nsew", padx=(12, 0), pady=(0, 14))
        right.grid_columnconfigure(0, weight=1)
        right.grid_columnconfigure(1, weight=0)

        self._section_header(right, "PAYLOAD", 0)
        self.payload_mode = ctk.CTkSegmentedButton(
            right,
            values=["Text", "File"],
            command=self.on_payload_mode_change,
            selected_color=COLORS["accent"],
            selected_hover_color=COLORS["accent_dim"],
            unselected_color=COLORS["surface"],
            unselected_hover_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            font=inter(12, "bold"),
            corner_radius=8,
        )
        self.payload_mode.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20, pady=(8, 12))
        self.payload_mode.set("Text")

        self.text_box = ctk.CTkTextbox(
            right,
            height=120,
            fg_color=COLORS["surface"],
            border_color=COLORS["border"],
            border_width=1,
            text_color=COLORS["text_primary"],
            scrollbar_button_color=COLORS["card"],
            scrollbar_button_hover_color=COLORS["border"],
            font=mono(12),
            corner_radius=8,
        )
        self.text_box.grid(row=2, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 16))
        self.text_box.bind("<KeyRelease>", lambda _event: self.update_capacity_preview())

        self.file_entry = ReusableWidgets.entry(right, "Choose any file", width=330)
        self.file_button = ReusableWidgets.ghost_button(right, "Browse File", self.browse_file, width=120)

        self._section_header(right, "ENCRYPTION", 3)
        ReusableWidgets.label(right, "Password", muted=True).grid(
            row=4, column=0, columnspan=2, sticky="w", padx=20
        )
        self.password_entry = ReusableWidgets.entry(right, "Password", show="•")
        self.password_entry.grid(row=5, column=0, columnspan=2, sticky="ew", padx=20, pady=(4, 10))
        self.password_entry.bind("<KeyRelease>", lambda _event: self.update_password_strength())

        ReusableWidgets.label(right, "Confirm Password", muted=True).grid(
            row=6, column=0, columnspan=2, sticky="w", padx=20
        )
        self.confirm_entry = ReusableWidgets.entry(right, "Confirm password", show="•")
        self.confirm_entry.grid(row=7, column=0, columnspan=2, sticky="ew", padx=20, pady=(4, 10))

        self.password_strength = ReusableWidgets.progress_bar(right, width=400)
        self.password_strength.grid(row=8, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 8))
        self.password_strength_label = ReusableWidgets.label(right, "Password strength", size=11, muted=True)
        self.password_strength_label.grid(row=9, column=0, columnspan=2, sticky="w", padx=20, pady=(0, 14))

        self._section_header(right, "OUTPUT", 10)
        self.output_entry = ReusableWidgets.entry(right, "Output PNG path", width=330)
        self.output_entry.grid(row=11, column=0, sticky="ew", padx=(20, 10), pady=(8, 18))
        choose = ReusableWidgets.ghost_button(right, "Choose Location", self.choose_output, width=150)
        choose.grid(row=11, column=1, sticky="e", padx=(0, 20), pady=(8, 18))

    def _build_action_row(self):
        action = ReusableWidgets.card(self.content, fg_color=COLORS["surface"])
        action.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        action.grid_columnconfigure(0, weight=1)

        self.encode_button = ReusableWidgets.primary_button(
            action,
            "ENCODE & HIDE",
            self.start_encode,
            width=220,
        )
        self.encode_button.grid(row=0, column=0, pady=(18, 10))

        self.status_label = ReusableWidgets.label(action, "", muted=True)
        self.status_label.grid(row=1, column=0, pady=(0, 8))
        self.status_label.grid_remove()

        self.operation_progress = ReusableWidgets.progress_bar(action, width=460)
        self.operation_progress.configure(mode="indeterminate")
        self.operation_progress.grid(row=2, column=0, pady=(0, 18))
        self.operation_progress.grid_remove()

        self.success_card = ReusableWidgets.card(self.content, border_width=1, border_color=COLORS["accent"])
        self.success_card.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        self.success_card.grid_columnconfigure(0, weight=1)
        ReusableWidgets.label(self.success_card, "ENCODE COMPLETE", size=14, weight="bold").grid(
            row=0, column=0, sticky="w", padx=18, pady=(14, 2)
        )
        self.success_details = ReusableWidgets.label(self.success_card, "", size=12, muted=True)
        self.success_details.grid(row=1, column=0, sticky="w", padx=18, pady=(0, 14))
        self.success_card.grid_remove()

    def _section_header(self, parent, text, row):
        ReusableWidgets.label(parent, text, size=12, weight="bold").grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            padx=20,
            pady=(18 if row == 0 else 8, 2),
        )

    def on_payload_mode_change(self, _value=None):
        if self.payload_mode.get() == "Text":
            self.file_entry.grid_remove()
            self.file_button.grid_remove()
            self.text_box.grid(row=2, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 16))
        else:
            self.text_box.grid_remove()
            self.file_entry.grid(row=2, column=0, sticky="ew", padx=(20, 10), pady=(0, 16))
            self.file_button.grid(row=2, column=1, sticky="e", padx=(0, 20), pady=(0, 16))
        self.update_capacity_preview()

    def browse_image(self):
        path = filedialog.askopenfilename(
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.bmp"),
                ("All files", "*.*"),
            ]
        )
        if not path:
            return

        try:
            with Image.open(path) as image:
                self.cover_image = image.copy()
        except Exception as exc:
            self.show_error(f"Could not load image: {exc}")
            return

        self.image_path = path
        self.preview.set_image(self.cover_image)
        capacity = max(FilePacker.max_file_size_for_image(self.cover_image), 0)
        self.capacity.update(0, capacity)
        self.image_info.configure(
            text=(
                f"{self.cover_image.width}x{self.cover_image.height} | "
                f"{self.cover_image.mode} | {capacity / (1024 * 1024):.2f} MB capacity"
            )
        )
        self.suggest_output_path(path)
        self.update_capacity_preview()

    def browse_file(self):
        path = filedialog.askopenfilename(filetypes=[("All files", "*.*")])
        if not path:
            return

        self.selected_file = path
        self.file_entry.delete(0, "end")
        self.file_entry.insert(0, path)
        self.update_capacity_preview()

    def choose_output(self):
        initial_dir = os.path.dirname(self.image_path) if self.image_path else os.getcwd()
        path = filedialog.asksaveasfilename(
            initialdir=initial_dir,
            defaultextension=".png",
            filetypes=[("PNG image", "*.png")],
        )
        if not path:
            return

        self.output_entry.delete(0, "end")
        self.output_entry.insert(0, path)

    def suggest_output_path(self, source_path):
        directory = os.path.dirname(source_path)
        stem = os.path.splitext(os.path.basename(source_path))[0]
        suggested = os.path.join(directory, f"{stem}_stegoxpress.png")
        self.output_entry.delete(0, "end")
        self.output_entry.insert(0, suggested)

    def update_password_strength(self):
        password = self.password_entry.get()
        length = len(password)

        if length == 0:
            self.password_strength.set(0)
            self.password_strength.configure(progress_color=COLORS["error"])
            self.password_strength_label.configure(text="Password strength")
        elif length < 8:
            self.password_strength.set(0.33)
            self.password_strength.configure(progress_color=COLORS["error"])
            self.password_strength_label.configure(text="Weak password")
        elif length < 12:
            self.password_strength.set(0.66)
            self.password_strength.configure(progress_color=COLORS["warning"])
            self.password_strength_label.configure(text="Medium password")
        else:
            self.password_strength.set(1.0)
            self.password_strength.configure(progress_color=COLORS["accent"])
            self.password_strength_label.configure(text="Strong password")

    def update_capacity_preview(self):
        if self.cover_image is None:
            return

        total = max(FilePacker.max_file_size_for_image(self.cover_image), 0)
        used = 0

        try:
            if self.payload_mode.get() == "Text":
                used = len(FilePacker.pack_text(self.text_box.get("1.0", "end-1c")))
            elif self.selected_file:
                used = len(FilePacker.pack_file(self.selected_file))
        except OSError:
            used = 0

        self.capacity.update(used, total)

    def start_encode(self):
        if self.cover_image is None:
            self.show_error("Load a cover image first.")
            return

        password = self.password_entry.get()
        confirm = self.confirm_entry.get()
        output_path = self.output_entry.get().strip()

        if not password:
            self.show_error("Enter a password.")
            return
        if password != confirm:
            self.show_error("Passwords do not match.")
            return
        if not output_path:
            self.show_error("Choose an output path.")
            return

        try:
            payload = self.build_payload()
        except ValueError as exc:
            self.show_error(str(exc))
            return
        except OSError as exc:
            self.show_error(f"Could not read payload: {exc}")
            return

        capacity = max(FilePacker.max_file_size_for_image(self.cover_image), 0)
        if capacity < len(payload):
            self.show_error(
                f"Image too small. Need {len(payload) / 1024:.1f}kb, "
                f"have {capacity / 1024:.1f}kb capacity."
            )
            return

        image = self.cover_image.copy()
        self.set_busy(True, "Encoding payload...")
        thread = threading.Thread(
            target=self.encode_worker,
            args=(image, payload, password, output_path),
            daemon=True,
        )
        thread.start()

    def build_payload(self):
        if self.payload_mode.get() == "Text":
            message = self.text_box.get("1.0", "end-1c")
            if not message:
                raise ValueError("Enter text to hide.")
            return FilePacker.pack_text(message)

        if not self.selected_file:
            raise ValueError("Choose a file to hide.")
        return FilePacker.pack_file(self.selected_file)

    def encode_worker(self, image, payload, password, output_path):
        try:
            encrypted = CryptoEngine.encrypt(payload, password)
            stego_image = LSBEngine.encode(image, encrypted)
            stego_image.save(output_path, "PNG")
            used_percent = LSBEngine.bits_used_percent(image, len(encrypted))
            self.ui_queue.put(
                (self.on_encode_success, (output_path, len(payload), used_percent))
            )
        except Exception as exc:
            self.ui_queue.put((self.show_error, (str(exc),)))

    def process_ui_queue(self):
        while True:
            try:
                callback, args = self.ui_queue.get_nowait()
            except queue.Empty:
                break
            callback(*args)

        self.after(100, self.process_ui_queue)

    def on_encode_success(self, output_path, payload_size, used_percent):
        self.set_busy(False, "Encoding complete.")
        self.success_details.configure(
            text=(
                f"{output_path}\n"
                f"Payload: {format_bytes(payload_size)} | Capacity used: {used_percent:.2f}%"
            )
        )
        self.success_card.grid()
        if self.on_encode_complete:
            self.on_encode_complete(output_path)
        self._notify_status("Ready")

    def set_busy(self, busy, text):
        self.status_label.configure(text=text, text_color=COLORS["text_muted"])
        self.status_label.grid()
        self.encode_button.configure(state="disabled" if busy else "normal")
        self._notify_status(text if busy else "Ready")

        if busy:
            self.operation_progress.grid()
            self.operation_progress.start()
            self.success_card.grid_remove()
        else:
            self.operation_progress.stop()
            self.operation_progress.grid_remove()

    def show_error(self, message):
        self.set_busy(False, message)
        self.status_label.configure(text=message, text_color=COLORS["error"])
        self._notify_status("Ready")

    def _notify_status(self, message):
        if self.status_callback:
            self.status_callback(message)
