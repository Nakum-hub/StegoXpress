import os
import queue
import threading
import time
from datetime import datetime
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image

from gui.widgets import COLORS, ReusableWidgets, inter
from transport.email_sender import EmailSender
from utils.config import Config
from utils.logger import StegoLogger


class SendTab(ctk.CTkFrame):
    def __init__(self, parent, on_send_success=None):
        super().__init__(parent, fg_color=COLORS["background"])
        self.on_send_success = on_send_success
        self.status_callback = None
        self.history_callback = None
        self.logger = StegoLogger.get()
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
        self.apply_config_defaults()
        self.after(100, self.process_ui_queue)

    def _build_left_column(self):
        left = ReusableWidgets.card(self.content)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12), pady=(0, 14))
        left.grid_columnconfigure(0, weight=1)
        left.grid_columnconfigure(1, weight=0)

        self._section_header(left, "STEGO IMAGE TO SEND", 0)
        self.image_entry = ReusableWidgets.entry(left, "Output PNG from Encode", width=420)
        self.image_entry.grid(row=1, column=0, sticky="ew", padx=(20, 10), pady=(10, 18))
        ReusableWidgets.ghost_button(left, "Browse", self.browse_image, width=110).grid(
            row=1,
            column=1,
            sticky="e",
            padx=(0, 20),
            pady=(10, 18),
        )

        self._section_header(left, "EMAIL PROVIDER", 2)
        self.provider_segment = ctk.CTkSegmentedButton(
            left,
            values=["Gmail", "Outlook", "Yahoo", "Custom"],
            command=self.on_provider_change,
            selected_color=COLORS["accent"],
            selected_hover_color=COLORS["accent_dim"],
            unselected_color=COLORS["surface"],
            unselected_hover_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            font=inter(12, "bold"),
            corner_radius=8,
        )
        self.provider_segment.grid(row=3, column=0, columnspan=2, sticky="ew", padx=20, pady=(10, 14))
        self.provider_segment.set(Config.get("default_provider").title())

        self.host_entry = ReusableWidgets.entry(left, "SMTP host", width=280)
        self.port_entry = ReusableWidgets.entry(left, "Port", width=110)
        self.host_entry.grid(row=4, column=0, sticky="ew", padx=(20, 10), pady=(0, 18))
        self.port_entry.grid(row=4, column=1, sticky="e", padx=(0, 20), pady=(0, 18))
        self.host_entry.grid_remove()
        self.port_entry.grid_remove()

        self._section_header(left, "CREDENTIALS", 5)
        ReusableWidgets.label(
            left,
            "Your credentials are used once and never stored on disk.",
            size=12,
            muted=True,
        ).grid(row=6, column=0, columnspan=2, sticky="w", padx=20, pady=(8, 10))

        self.sender_entry = ReusableWidgets.entry(left, "Sender email", width=420)
        self.sender_entry.grid(row=7, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 10))
        self.password_entry = ReusableWidgets.entry(left, "App password", width=420, show="•")
        self.password_entry.grid(row=8, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 12))

        ReusableWidgets.ghost_button(
            left,
            "Test Connection",
            self.start_test_connection,
            width=170,
        ).grid(row=9, column=0, sticky="w", padx=20, pady=(0, 18))
        self.test_result = ReusableWidgets.label(left, "", size=12, muted=True)
        self.test_result.grid(row=9, column=1, sticky="e", padx=20, pady=(0, 18))

    def _build_right_column(self):
        right = ReusableWidgets.card(self.content)
        right.grid(row=0, column=1, sticky="nsew", padx=(12, 0), pady=(0, 14))
        right.grid_columnconfigure(0, weight=1)

        self._section_header(right, "RECIPIENT", 0)
        self.recipient_entry = ReusableWidgets.entry(right, "Recipient email", width=420)
        self.recipient_entry.grid(row=1, column=0, sticky="ew", padx=20, pady=(10, 12))

        self.hint_entry = ReusableWidgets.entry(
            right,
            "Password hint for recipient (do NOT put the password here)",
            width=420,
        )
        self.hint_entry.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 18))

        note = (
            "Only the stego image is attached. The agreed decode password must be "
            "shared through a separate channel."
        )
        ctk.CTkLabel(
            right,
            text=note,
            text_color=COLORS["text_muted"],
            font=inter(12),
            wraplength=400,
            justify="left",
        ).grid(row=3, column=0, sticky="w", padx=20, pady=(0, 18))

    def _build_action_row(self):
        action = ReusableWidgets.card(self.content, fg_color=COLORS["surface"])
        action.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        action.grid_columnconfigure(0, weight=1)

        self.send_button = ReusableWidgets.primary_button(
            action,
            "SEND IMAGE",
            self.start_send,
            width=220,
        )
        self.send_button.grid(row=0, column=0, pady=(18, 10))

        self.status_label = ReusableWidgets.label(action, "", muted=True)
        self.status_label.grid(row=1, column=0, padx=20, pady=(0, 18))
        self.status_label.grid_remove()

    def _section_header(self, parent, text, row):
        ReusableWidgets.label(parent, text, size=12, weight="bold").grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            padx=20,
            pady=(18 if row == 0 else 8, 2),
        )

    def browse_image(self):
        path = filedialog.askopenfilename(
            filetypes=[
                ("PNG image", "*.png"),
                ("All files", "*.*"),
            ]
        )
        if path:
            self.set_image_path(path)

    def set_image_path(self, path):
        self.image_entry.delete(0, "end")
        self.image_entry.insert(0, path)

    def on_provider_change(self, _value=None):
        if self.provider_segment.get() == "Custom":
            self.host_entry.grid()
            self.port_entry.grid()
        else:
            self.host_entry.grid_remove()
            self.port_entry.grid_remove()

    def get_sender(self):
        provider = self.provider_segment.get().lower()
        if provider == "custom":
            host = self.host_entry.get().strip()
            port_text = self.port_entry.get().strip()
            if not host or not port_text:
                raise ValueError("Custom SMTP host and port are required.")
            try:
                port = int(port_text)
            except ValueError as exc:
                raise ValueError("Custom SMTP port must be a number.") from exc
            return EmailSender(provider, host=host, port=port)

        return EmailSender(provider)

    def collect_credentials(self):
        username = self.sender_entry.get().strip()
        password = self.password_entry.get()

        if not username:
            raise ValueError("Enter the sender email.")
        if not password:
            raise ValueError("Enter the app password.")

        return username, password

    def collect_send_fields(self):
        image_path = self.image_entry.get().strip()
        username, password = self.collect_credentials()

        if not image_path:
            raise ValueError("Choose a stego image to send.")
        if not os.path.exists(image_path):
            raise ValueError("The selected stego image does not exist.")

        return image_path, username, password

    def apply_config_defaults(self):
        provider = Config.get("default_provider")
        if provider:
            self.provider_segment.set(provider.title())
            self.on_provider_change()

        if Config.get("remember_sender_email"):
            self.sender_entry.delete(0, "end")
            self.sender_entry.insert(0, Config.get("sender_email") or "")

    def start_test_connection(self):
        try:
            username, password = self.collect_credentials()
            sender = self.get_sender()
        except ValueError as exc:
            self.show_test_result(False, str(exc))
            return

        self.test_result.configure(text="Testing...", text_color=COLORS["text_muted"])
        self._notify_status("Testing SMTP connection...")
        thread = threading.Thread(
            target=self.test_connection_worker,
            args=(sender, username, password),
            daemon=True,
        )
        thread.start()

    def test_connection_worker(self, sender, username, password):
        try:
            ok = sender.test_connection(username, password)
            message = "✓ Connected" if ok else "✗ Login failed"
            self.ui_queue.put((self.show_test_result, (ok, message)))
        except Exception as exc:
            self.ui_queue.put((self.show_test_result, (False, f"✗ {exc}")))

    def start_send(self):
        try:
            image_path, username, password = self.collect_send_fields()
            recipient = self.recipient_entry.get().strip()
            hint = self.hint_entry.get().strip()
            sender = self.get_sender()
        except ValueError as exc:
            self.fail_send_validation(str(exc))
            return

        if not recipient:
            self.fail_send_validation("Enter the recipient email.")
            return

        self.set_busy(True, f"Sending image to {recipient}...")
        thread = threading.Thread(
            target=self.send_worker,
            args=(sender, username, password, recipient, image_path, hint),
            daemon=True,
        )
        thread.start()

    def send_worker(self, sender, username, password, recipient, image_path, hint):
        start_time = time.perf_counter()
        image_size = os.path.getsize(image_path) if os.path.exists(image_path) else 0
        dimensions = self.image_dimensions(image_path)
        description = f"Sent {os.path.basename(image_path)} to {recipient}"
        try:
            sender.send_stego_image(username, password, recipient, image_path, hint)
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.log_operation(
                "send",
                dimensions,
                image_size,
                True,
                "",
                duration_ms,
            )
            self.ui_queue.put((self.on_send_complete, (recipient, duration_ms, description)))
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            reason = str(exc)
            self.log_operation(
                "send",
                dimensions,
                image_size,
                False,
                reason,
                duration_ms,
            )
            self.ui_queue.put((self.on_send_failure, (reason, duration_ms, description)))

    def on_send_complete(self, recipient, duration_ms, description):
        self.set_busy(False, f"Image sent to {recipient}")
        self.status_label.configure(text_color=COLORS["accent"])
        self.persist_sender_email()
        self.add_history("send", description, True, duration_ms)
        if self.on_send_success:
            self.on_send_success(recipient)
        self._notify_status("Ready")

    def on_send_failure(self, reason, duration_ms, description):
        self.show_error(reason)
        self.add_history("send", description, False, duration_ms, reason)

    def persist_sender_email(self):
        Config.set("default_provider", self.provider_segment.get().lower())
        if Config.get("remember_sender_email"):
            Config.set("sender_email", self.sender_entry.get().strip())

    def image_dimensions(self, image_path):
        try:
            with Image.open(image_path) as image:
                return f"{image.width}x{image.height}"
        except Exception:
            return "unknown"

    def log_operation(self, operation, image_dimensions, payload_size, success, reason, duration_ms):
        self.logger.info(
            "operation=%s timestamp=%s image_dimensions=%s payload_size=%s "
            "success=%s reason=%s duration_ms=%.0f",
            operation,
            datetime.now().isoformat(timespec="seconds"),
            image_dimensions,
            payload_size,
            success,
            reason or "-",
            duration_ms,
        )

    def add_history(self, op_type, description, success, duration_ms, reason=""):
        if self.history_callback:
            self.history_callback(op_type, description, success, duration_ms, reason)

    def show_test_result(self, success, message):
        self.test_result.configure(
            text=message,
            text_color=COLORS["accent"] if success else COLORS["error"],
        )
        self._notify_status("Ready")

    def set_busy(self, busy, message):
        self.status_label.configure(text=message, text_color=COLORS["text_muted"])
        self.status_label.grid()
        self.send_button.configure(state="disabled" if busy else "normal")
        self._notify_status(message if busy else "Ready")

    def show_error(self, message):
        self.set_busy(False, message)
        self.status_label.configure(text=message, text_color=COLORS["error"])
        self._notify_status("Ready")

    def fail_send_validation(self, reason):
        self.show_error(reason)
        self.log_operation(
            "send",
            "unknown",
            0,
            False,
            reason,
            0,
        )
        self.add_history("send", "Send request blocked before processing", False, 0, reason)

    def process_ui_queue(self):
        while True:
            try:
                callback, args = self.ui_queue.get_nowait()
            except queue.Empty:
                break
            callback(*args)

        self.after(100, self.process_ui_queue)

    def _notify_status(self, message):
        if self.status_callback:
            self.status_callback(message)
