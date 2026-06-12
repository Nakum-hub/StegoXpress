import os
import queue
import threading
import time
from datetime import datetime
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image

from core.audio_engine import AudioEngine
from core.crypto_engine import CryptoEngine
from core.file_packer import FilePacker
from core.lsb_engine import LSBEngine
from core.png_chunk_engine import PngChunkEngine
from gui.dnd import enable_image_drop
from gui.widgets import COLORS, ReusableWidgets, format_bytes, inter, mono
from utils.logger import StegoLogger


class DecodeTab(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=COLORS["background"])
        self.status_callback = None
        self.history_callback = None
        self.logger = StegoLogger.get()
        self.image_path = None
        self.stego_image = None
        self.audio_path = None
        self.result = None
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

        self._build_input_area()
        self._build_results_area()
        self.setup_drag_and_drop()
        self.after(100, self.process_ui_queue)

    CARRIERS = ["Image (LSB)", "Audio (WAV)", "PNG Metadata"]

    def _build_input_area(self):
        left = ReusableWidgets.card(self.content)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12), pady=(0, 14))
        left.grid_columnconfigure(0, weight=1)

        self._section_header(left, "CARRIER TYPE", 0)
        self.carrier_selector = ctk.CTkSegmentedButton(
            left, values=self.CARRIERS,
            command=self._on_carrier_change,
            selected_color=COLORS["accent"],
            selected_hover_color=COLORS["accent_dim"],
            unselected_color=COLORS["surface"],
            unselected_hover_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            font=inter(11, "bold"), corner_radius=8,
        )
        self.carrier_selector.grid(row=1, column=0, sticky="ew", padx=20, pady=(8, 4))
        self.carrier_selector.set("Image (LSB)")

        # Audio browse row (hidden by default)
        self.audio_frame = ctk.CTkFrame(left, fg_color="transparent")
        self.audio_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 6))
        self.audio_frame.grid_columnconfigure(0, weight=1)
        self.audio_entry = ReusableWidgets.entry(self.audio_frame, "Select .wav file…")
        self.audio_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ReusableWidgets.ghost_button(
            self.audio_frame, "Browse", self._browse_audio, width=70
        ).grid(row=0, column=1)
        self.audio_frame.grid_remove()

        self._section_header(left, "STEGO IMAGE", 3)
        self.preview = ReusableWidgets.image_preview(left, size=280)
        self.preview.grid(row=1, column=0, pady=(10, 12))

        browse = ReusableWidgets.ghost_button(left, "Browse Stego Image", self.browse_image)
        browse.grid(row=2, column=0, pady=(0, 14))

        self.image_info = ReusableWidgets.label(left, "No image selected", muted=True)
        self.image_info.grid(row=3, column=0, sticky="w", padx=20, pady=(0, 18))

        right = ReusableWidgets.card(self.content)
        right.grid(row=0, column=1, sticky="nsew", padx=(12, 0), pady=(0, 14))
        right.grid_columnconfigure(0, weight=1)

        self._section_header(right, "DECRYPTION", 0)
        ReusableWidgets.label(right, "Password", muted=True).grid(row=1, column=0, sticky="w", padx=20, pady=(8, 0))
        self.password_entry = ReusableWidgets.entry(right, "Password", show="•")
        self.password_entry.grid(row=2, column=0, sticky="ew", padx=20, pady=(4, 16))

        self.decode_button = ReusableWidgets.primary_button(
            right,
            "DECODE & EXTRACT",
            self.start_decode,
            width=220,
        )
        self.decode_button.grid(row=3, column=0, pady=(0, 12))

        self.status_label = ReusableWidgets.label(right, "", muted=True)
        self.status_label.grid(row=4, column=0, padx=20, pady=(0, 18))
        self.status_label.grid_remove()

    def _build_results_area(self):
        self.results_card = ReusableWidgets.card(
            self.content,
            border_width=1,
            border_color=COLORS["border"],
        )
        self.results_card.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        self.results_card.grid_columnconfigure(0, weight=1)

        ReusableWidgets.label(self.results_card, "EXTRACTED CONTENT", size=14, weight="bold").grid(
            row=0,
            column=0,
            sticky="w",
            padx=18,
            pady=(16, 8),
        )

        self.result_textbox = ctk.CTkTextbox(
            self.results_card,
            height=150,
            fg_color=COLORS["surface"],
            border_color=COLORS["border"],
            border_width=1,
            text_color=COLORS["text_primary"],
            scrollbar_button_color=COLORS["card"],
            scrollbar_button_hover_color=COLORS["border"],
            font=mono(12),
            corner_radius=8,
        )

        self.file_result_label = ReusableWidgets.label(self.results_card, "", size=13, muted=True)
        self.copy_button = ReusableWidgets.ghost_button(
            self.results_card,
            "Copy to Clipboard",
            self.copy_text,
            width=180,
        )
        self.save_button = ReusableWidgets.primary_button(
            self.results_card,
            "Save File As...",
            self.save_file_as,
            width=180,
        )
        self.clear_button = ReusableWidgets.ghost_button(
            self.results_card,
            "Clear",
            self.clear,
            width=120,
        )
        self.results_card.grid_remove()

    def _section_header(self, parent, text, row):
        ReusableWidgets.label(parent, text, size=12, weight="bold").grid(
            row=row,
            column=0,
            sticky="w",
            padx=20,
            pady=(18 if row == 0 else 8, 2),
        )

    def _on_carrier_change(self, value):
        if value == "Audio (WAV)":
            self.audio_frame.grid()
        else:
            self.audio_frame.grid_remove()

    def _browse_audio(self):
        from tkinter import filedialog as _fd
        path = _fd.askopenfilename(
            title="Select WAV File",
            filetypes=[("WAV files", "*.wav"), ("All", "*.*")]
        )
        if path:
            self.audio_path = path
            self.audio_entry.delete(0, "end")
            self.audio_entry.insert(0, path)

    def browse_image(self):
        path = filedialog.askopenfilename(
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.bmp"),
                ("All files", "*.*"),
            ]
        )
        if path:
            self.load_image_path(path)

    def load_image_path(self, path):
        try:
            with Image.open(path) as image:
                self.stego_image = image.copy()
        except Exception as exc:
            self.show_error(f"Could not load image: {exc}")
            return

        self.image_path = path
        self.preview.set_image(self.stego_image)
        file_size = os.path.getsize(path)
        self.image_info.configure(
            text=(
                f"{format_bytes(file_size)} | "
                f"{self.stego_image.width}x{self.stego_image.height} | "
                f"{self.stego_image.mode}"
            )
        )
        self.hide_results()
        self.status_label.grid_remove()

    def setup_drag_and_drop(self):
        enable_image_drop(
            self.preview,
            self.load_image_path,
            self.show_error,
            self.highlight_drop_zone,
        )

    def highlight_drop_zone(self, active):
        self.preview.configure(fg_color=COLORS["accent"] if active else COLORS["surface"])

    def start_decode(self):
        carrier = self.carrier_selector.get() if hasattr(self, "carrier_selector") else "Image (LSB)"

        if carrier == "Audio (WAV)":
            if not self.audio_path or not os.path.exists(self.audio_path):
                self.fail_decode_validation("Select a WAV audio file first."); return
        elif self.stego_image is None:
            self.fail_decode_validation("Load a stego image first."); return

        password = self.password_entry.get()
        if not password:
            self.fail_decode_validation("Enter the password."); return

        image = self.stego_image.copy() if self.stego_image else None
        image_path = self.image_path
        self.set_busy(True, "Decoding…")
        thread = threading.Thread(
            target=self.decode_worker,
            args=(image, password, image_path, carrier),
            daemon=True,
        )
        thread.start()

    def decode_worker(self, image, password, image_path, carrier="Image (LSB)"):
        start_time = time.perf_counter()
        payload_size = 0
        try:
            # Extract raw encrypted bytes from the chosen carrier
            if carrier == "Audio (WAV)":
                raw_encrypted = AudioEngine.decode(self.audio_path)
            elif carrier == "PNG Metadata":
                raw_encrypted = PngChunkEngine.decode(image_path)
            else:
                if hasattr(self, '_use_adaptive') and self._use_adaptive:
                    raw_encrypted = LSBEngine.decode_adaptive(image)
                else:
                    raw_encrypted = LSBEngine.decode(image)

            payload_size = len(raw_encrypted)

            try:
                payload = CryptoEngine.decrypt(raw_encrypted, password)
            except ValueError as exc:
                raise ValueError("Wrong password or not a StegoXpress image") from exc

            # Handle sealed payloads
            if FilePacker.is_sealed(payload):
                result = FilePacker.verify_and_unpack_sealed(payload, password)
                result["_seal_verified"] = True
            else:
                result = FilePacker.unpack(payload)
                result["_seal_verified"] = False

            payload_size = len(payload)
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.log_operation("decode", image, payload_size, True, "", duration_ms)
            self.ui_queue.put((self.show_result, (result, duration_ms, image_path)))
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            reason = str(exc)
            self.log_operation("decode", image, payload_size, False, reason, duration_ms)
            self.ui_queue.put((self.on_decode_failure, (reason, duration_ms, image_path)))

    def process_ui_queue(self):
        while True:
            try:
                callback, args = self.ui_queue.get_nowait()
            except queue.Empty:
                break
            callback(*args)

        self.after(100, self.process_ui_queue)

    def show_result(self, result, duration_ms=0, image_path=None):
        self.result = result
        self.set_busy(False, "Decode complete.")
        # Seal badge
        if result.get("_seal_verified"):
            self._notify_status("✓ Seal verified — image untampered")
        # Self-destruct warning
        rtype = result.get("type", "")
        if "self_destruct" in rtype:
            self._show_self_destruct_warning(image_path)
        self.hide_results()
        self.results_card.grid()

        if result["type"] == "text":
            description = (
                f"Decoded text ({len(result['data'])} bytes) from "
                f"{os.path.basename(image_path or self.image_path or 'image')}"
            )
            self.result_textbox.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 12))
            self.result_textbox.configure(state="normal")
            self.result_textbox.delete("1.0", "end")
            self.result_textbox.insert("1.0", result["text"])
            self.result_textbox.configure(state="disabled")
            self.copy_button.grid(row=2, column=0, sticky="w", padx=18, pady=(0, 14))
        else:
            description = (
                f"Decoded file '{result['filename']}' from "
                f"{os.path.basename(image_path or self.image_path or 'image')}"
            )
            self.file_result_label.configure(
                text=f"{result['filename']} | {format_bytes(len(result['data']))}"
            )
            self.file_result_label.grid(row=1, column=0, sticky="w", padx=18, pady=(0, 12))
            self.save_button.grid(row=2, column=0, sticky="w", padx=18, pady=(0, 14))

        self.clear_button.grid(row=3, column=0, sticky="w", padx=18, pady=(0, 16))
        self.add_history("decode", description, True, duration_ms)
        self._notify_status("Ready")

    def on_decode_failure(self, reason, duration_ms, image_path):
        self.show_error(reason)
        description = f"Decode failed for {os.path.basename(image_path or 'image')}"
        self.add_history("decode", description, False, duration_ms, reason)

    def fail_decode_validation(self, reason):
        self.show_error(reason)
        self.log_operation("decode", self.stego_image, 0, False, reason, 0)
        self.add_history("decode", "Decode request blocked before processing", False, 0, reason)

    def _show_self_destruct_warning(self, image_path):
        """Show dialog warning user that the image will be erased after they dismiss."""
        if not image_path or not os.path.exists(image_path):
            return
        dialog = ctk.CTkToplevel(self)
        dialog.title("⚠ SELF-DESTRUCT")
        dialog.geometry("440x220")
        dialog.configure(fg_color=COLORS["background"])
        dialog.transient(self)
        dialog.grab_set()
        dialog.lift()
        ReusableWidgets.label(dialog, "⚠  SELF-DESTRUCT MODE", size=16, weight="bold").pack(
            padx=20, pady=(20, 8))
        ReusableWidgets.label(
            dialog,
            "This message will be erased from the image after you close this dialog.
"
            "Save or copy the content NOW before closing.",
            size=12, muted=True).pack(padx=20, pady=(0, 14))

        def erase_and_close():
            try:
                img = Image.open(image_path)
                erased = LSBEngine.erase(img)
                erased.save(image_path, "PNG")
                self._notify_status("✓ Image erased — hidden data removed")
            except Exception as exc:
                self._notify_status(f"Erase failed: {exc}")
            dialog.destroy()

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack()
        ReusableWidgets.ghost_button(btn_row, "Keep Image", dialog.destroy, width=140).pack(
            side="left", padx=8)
        ctk.CTkButton(btn_row, text="Erase Image Now",
                      fg_color=COLORS["error"], hover_color="#cc3333",
                      text_color="white", font=inter(12, "bold"),
                      width=160, command=erase_and_close).pack(side="left", padx=8)

    def log_operation(self, operation, image, payload_size, success, reason, duration_ms):
        dimensions = f"{image.width}x{image.height}" if image is not None else "unknown"
        self.logger.info(
            "operation=%s timestamp=%s image_dimensions=%s payload_size=%s "
            "success=%s reason=%s duration_ms=%.0f",
            operation,
            datetime.now().isoformat(timespec="seconds"),
            dimensions,
            payload_size,
            success,
            reason or "-",
            duration_ms,
        )

    def add_history(self, op_type, description, success, duration_ms, reason=""):
        if self.history_callback:
            self.history_callback(op_type, description, success, duration_ms, reason)

    def hide_results(self):
        self.result_textbox.grid_remove()
        self.file_result_label.grid_remove()
        self.copy_button.grid_remove()
        self.save_button.grid_remove()
        self.clear_button.grid_remove()
        self.results_card.grid_remove()

    def copy_text(self):
        if not self.result or self.result["type"] != "text":
            return
        self.clipboard_clear()
        self.clipboard_append(self.result["text"])
        self.status_label.configure(text="Copied to clipboard.", text_color=COLORS["accent"])
        self.status_label.grid()

    def save_file_as(self):
        if not self.result or self.result["type"] != "file":
            return

        path = filedialog.asksaveasfilename(initialfile=self.result["filename"])
        if not path:
            return

        with open(path, "wb") as output:
            output.write(self.result["data"])

        self.status_label.configure(text=f"Saved to {path}", text_color=COLORS["accent"])
        self.status_label.grid()

    def clear(self):
        self.result = None
        self.password_entry.delete(0, "end")
        self.status_label.grid_remove()
        self.hide_results()

    def set_busy(self, busy, text):
        self.status_label.configure(text=text, text_color=COLORS["text_muted"])
        self.status_label.grid()
        self.decode_button.configure(state="disabled" if busy else "normal")
        self._notify_status(text if busy else "Ready")

    def show_error(self, message):
        self.set_busy(False, message)
        self.status_label.configure(text=message, text_color=COLORS["error"])
        self._notify_status("Ready")

    def _notify_status(self, message):
        if self.status_callback:
            self.status_callback(message)
