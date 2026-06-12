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
from utils.config import Config
from utils.logger import StegoLogger


class EncodeTab(ctk.CTkFrame):
    CARRIERS = ["Image (LSB)", "Audio (WAV)", "PNG Metadata"]

    def __init__(self, parent, on_encode_complete: callable):
        super().__init__(parent, fg_color=COLORS["background"])
        self.on_encode_complete = on_encode_complete
        self.status_callback = None
        self.history_callback = None
        self.logger = StegoLogger.get()
        self.image_path    = None
        self.cover_image   = None
        self.selected_file = None
        self.audio_path    = None
        self._heatmap_img  = None
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
        self.setup_drag_and_drop()
        self.after(100, self.process_ui_queue)

    # ── Left column ───────────────────────────────────────────────────────────

    def _build_left_column(self):
        left = ReusableWidgets.card(self.content)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12), pady=(0, 14))
        left.grid_columnconfigure(0, weight=1)

        self._section_header(left, "COVER IMAGE", 0)
        self.preview = ReusableWidgets.image_preview(left, size=280)
        self.preview.grid(row=1, column=0, pady=(10, 6))

        # Heatmap toggle (hidden until image loaded)
        self.heatmap_toggle = ctk.CTkSegmentedButton(
            left, values=["Original", "Heatmap"],
            command=self._on_heatmap_toggle,
            selected_color=COLORS["accent"],
            selected_hover_color=COLORS["accent_dim"],
            unselected_color=COLORS["surface"],
            unselected_hover_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            font=inter(11), corner_radius=8, width=240,
        )
        self.heatmap_toggle.set("Original")
        self.heatmap_toggle.grid(row=2, column=0, pady=(0, 8))
        self.heatmap_toggle.grid_remove()

        browse = ReusableWidgets.ghost_button(left, "Browse Image", self.browse_image)
        browse.grid(row=3, column=0, pady=(0, 14))

        # Audio browse (hidden until Audio carrier selected)
        self.audio_browse_frame = ctk.CTkFrame(left, fg_color="transparent")
        self.audio_browse_frame.grid(row=4, column=0, sticky="ew", padx=20, pady=(0, 8))
        self.audio_browse_frame.grid_columnconfigure(0, weight=1)
        ReusableWidgets.label(self.audio_browse_frame, "WAV AUDIO FILE", size=11, muted=True).grid(
            row=0, column=0, columnspan=2, sticky="w")
        self.audio_entry = ReusableWidgets.entry(self.audio_browse_frame, "Select .wav file…")
        self.audio_entry.grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=(4, 0))
        ReusableWidgets.ghost_button(
            self.audio_browse_frame, "Browse", self._browse_audio, width=70
        ).grid(row=1, column=1, pady=(4, 0))
        self.audio_info = ReusableWidgets.label(
            self.audio_browse_frame, "Only 16-bit PCM WAV supported.", size=10, muted=True)
        self.audio_info.grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 0))
        self.audio_browse_frame.grid_remove()

        self.capacity = ReusableWidgets.capacity_bar(left, width=360)
        self.capacity.grid(row=5, column=0, sticky="ew", padx=20, pady=(0, 12))

        self.image_info = ReusableWidgets.label(left, "No image selected", muted=True)
        self.image_info.grid(row=6, column=0, sticky="w", padx=20, pady=(0, 18))

    # ── Right column ──────────────────────────────────────────────────────────

    def _build_right_column(self):
        right = ReusableWidgets.card(self.content)
        right.grid(row=0, column=1, sticky="nsew", padx=(12, 0), pady=(0, 14))
        right.grid_columnconfigure(0, weight=1)
        right.grid_columnconfigure(1, weight=0)

        # CARRIER TYPE
        self._section_header(right, "CARRIER TYPE", 0)
        self.carrier_selector = ctk.CTkSegmentedButton(
            right, values=self.CARRIERS,
            command=self._on_carrier_change,
            selected_color=COLORS["accent"],
            selected_hover_color=COLORS["accent_dim"],
            unselected_color=COLORS["surface"],
            unselected_hover_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            font=inter(11, "bold"), corner_radius=8,
        )
        self.carrier_selector.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20, pady=(8, 12))
        self.carrier_selector.set("Image (LSB)")

        self.carrier_note = ReusableWidgets.label(
            right, "LSB into RGB pixels — stego image saved as PNG.", size=10, muted=True)
        self.carrier_note.grid(row=2, column=0, columnspan=2, sticky="w", padx=20, pady=(0, 10))

        # PAYLOAD
        self._section_header(right, "PAYLOAD", 3)
        self.payload_mode = ctk.CTkSegmentedButton(
            right, values=["Text", "File"],
            command=self.on_payload_mode_change,
            selected_color=COLORS["accent"],
            selected_hover_color=COLORS["accent_dim"],
            unselected_color=COLORS["surface"],
            unselected_hover_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            font=inter(12, "bold"), corner_radius=8,
        )
        self.payload_mode.grid(row=4, column=0, columnspan=2, sticky="ew", padx=20, pady=(8, 12))
        self.payload_mode.set("Text")

        self.text_box = ctk.CTkTextbox(
            right, height=120,
            fg_color=COLORS["surface"], border_color=COLORS["border"],
            border_width=1, text_color=COLORS["text_primary"],
            scrollbar_button_color=COLORS["card"],
            scrollbar_button_hover_color=COLORS["border"],
            font=mono(12), corner_radius=8,
        )
        self.text_box.grid(row=5, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 16))
        self.text_box.bind("<KeyRelease>", lambda _: self.update_capacity_preview())

        self.file_entry  = ReusableWidgets.entry(right, "Choose any file", width=330)
        self.file_button = ReusableWidgets.ghost_button(right, "Browse File", self.browse_file, width=120)

        # ENCRYPTION
        self._section_header(right, "ENCRYPTION", 6)
        ReusableWidgets.label(right, "Password", muted=True).grid(
            row=7, column=0, columnspan=2, sticky="w", padx=20)
        self.password_entry = ReusableWidgets.entry(right, "Password", show="•")
        self.password_entry.grid(row=8, column=0, columnspan=2, sticky="ew", padx=20, pady=(4, 10))
        self.password_entry.bind("<KeyRelease>", lambda _: self.update_password_strength())

        ReusableWidgets.label(right, "Confirm Password", muted=True).grid(
            row=9, column=0, columnspan=2, sticky="w", padx=20)
        self.confirm_entry = ReusableWidgets.entry(right, "Confirm password", show="•")
        self.confirm_entry.grid(row=10, column=0, columnspan=2, sticky="ew", padx=20, pady=(4, 10))

        self.password_strength = ReusableWidgets.progress_bar(right, width=400)
        self.password_strength.grid(row=11, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 4))
        self.password_strength_label = ReusableWidgets.label(
            right, "Password strength", size=11, muted=True)
        self.password_strength_label.grid(row=12, column=0, columnspan=2, sticky="w", padx=20, pady=(0, 10))

        # Seal / self-destruct / adaptive switches
        switches_frame = ctk.CTkFrame(right, fg_color="transparent")
        switches_frame.grid(row=13, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 10))

        self.seal_switch = ctk.CTkSwitch(
            switches_frame, text="Tamper-Proof Seal",
            fg_color=COLORS["border"], progress_color=COLORS["accent"],
            font=inter(12), text_color=COLORS["text_primary"],
        )
        self.seal_switch.grid(row=0, column=0, sticky="w", pady=3)
        ReusableWidgets.label(
            switches_frame, "Decode fails if image is modified", size=10, muted=True
        ).grid(row=1, column=0, sticky="w", padx=(28, 0), pady=(0, 6))

        self.destruct_switch = ctk.CTkSwitch(
            switches_frame, text="Self-Destruct After Decode",
            fg_color=COLORS["border"], progress_color=COLORS["error"],
            font=inter(12), text_color=COLORS["text_primary"],
        )
        self.destruct_switch.grid(row=2, column=0, sticky="w", pady=3)
        ReusableWidgets.label(
            switches_frame, "Image becomes unreadable after first decode", size=10, muted=True
        ).grid(row=3, column=0, sticky="w", padx=(28, 0), pady=(0, 6))

        self.adaptive_switch = ctk.CTkSwitch(
            switches_frame, text="Adaptive LSB (hide in texture regions only)",
            fg_color=COLORS["border"], progress_color=COLORS["accent_dim"],
            font=inter(12), text_color=COLORS["text_primary"],
        )
        self.adaptive_switch.grid(row=4, column=0, sticky="w", pady=3)
        ReusableWidgets.label(
            switches_frame, "Reduces steganalysis detectability on complex images",
            size=10, muted=True
        ).grid(row=5, column=0, sticky="w", padx=(28, 0), pady=(0, 4))

        # OUTPUT
        self._section_header(right, "OUTPUT", 14)
        self.output_entry = ReusableWidgets.entry(right, "Output path", width=330)
        self.output_entry.grid(row=15, column=0, sticky="ew", padx=(20, 10), pady=(8, 18))
        choose = ReusableWidgets.ghost_button(
            right, "Choose Location", self.choose_output, width=150)
        choose.grid(row=15, column=1, sticky="e", padx=(0, 20), pady=(8, 18))

    # ── Action row ────────────────────────────────────────────────────────────

    def _build_action_row(self):
        action = ReusableWidgets.card(self.content, fg_color=COLORS["surface"])
        action.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        action.grid_columnconfigure(0, weight=1)

        self.encode_button = ReusableWidgets.primary_button(
            action, "ENCODE & HIDE", self.start_encode, width=220)
        self.encode_button.grid(row=0, column=0, pady=(18, 10))

        self.status_label = ReusableWidgets.label(action, "", muted=True)
        self.status_label.grid(row=1, column=0, pady=(0, 8))
        self.status_label.grid_remove()

        self.operation_progress = ReusableWidgets.progress_bar(action, width=460)
        self.operation_progress.configure(mode="indeterminate")
        self.operation_progress.grid(row=2, column=0, pady=(0, 18))
        self.operation_progress.grid_remove()

        self.success_card = ReusableWidgets.card(
            self.content, border_width=1, border_color=COLORS["accent"])
        self.success_card.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        self.success_card.grid_columnconfigure(0, weight=1)
        ReusableWidgets.label(
            self.success_card, "ENCODE COMPLETE", size=14, weight="bold"
        ).grid(row=0, column=0, sticky="w", padx=18, pady=(14, 2))
        self.success_details = ReusableWidgets.label(self.success_card, "", size=12, muted=True)
        self.success_details.grid(row=1, column=0, sticky="w", padx=18, pady=(0, 6))
        self.steg_score_label = ReusableWidgets.label(self.success_card, "", size=12)
        self.steg_score_label.grid(row=2, column=0, sticky="w", padx=18, pady=(0, 4))
        self.steg_score_bar = ReusableWidgets.progress_bar(self.success_card, width=440)
        self.steg_score_bar.grid(row=3, column=0, sticky="w", padx=18, pady=(0, 14))
        self.success_card.grid_remove()

    # ── Section header helper ─────────────────────────────────────────────────

    def _section_header(self, parent, text, row):
        ReusableWidgets.label(parent, text, size=12, weight="bold").grid(
            row=row, column=0, columnspan=2,
            sticky="w", padx=20, pady=(14, 0))

    # ── Carrier change ────────────────────────────────────────────────────────

    def _on_carrier_change(self, value):
        notes = {
            "Image (LSB)":   "LSB into RGB pixels — stego image saved as PNG.",
            "Audio (WAV)":   "LSB into 16-bit PCM WAV samples — output saved as WAV.",
            "PNG Metadata":  "Hidden in private PNG chunk — pixels visually unchanged. ~2 GB capacity.",
        }
        self.carrier_note.configure(text=notes.get(value, ""))
        if value == "Audio (WAV)":
            self.preview.grid_remove()
            self.heatmap_toggle.grid_remove()
            self.audio_browse_frame.grid()
        else:
            self.audio_browse_frame.grid_remove()
            self.preview.grid()
        # Adaptive only makes sense for Image LSB
        self.adaptive_switch.configure(
            state="normal" if value == "Image (LSB)" else "disabled")
        if value != "Image (LSB)":
            self.adaptive_switch.deselect()

    def _browse_audio(self):
        path = filedialog.askopenfilename(
            title="Select WAV File",
            filetypes=[("WAV files", "*.wav"), ("All", "*.*")]
        )
        if not path:
            return
        self.audio_path = path
        self.audio_entry.delete(0, "end")
        self.audio_entry.insert(0, path)
        try:
            cap = AudioEngine.capacity_bytes(path)
            self.audio_info.configure(
                text=f"Capacity: {format_bytes(cap)} available (16-bit PCM)",
                text_color=COLORS["text_primary"])
            self.suggest_output_path(path)
        except Exception as exc:
            self.audio_info.configure(text=f"Error: {exc}", text_color=COLORS["error"])

    # ── Heatmap toggle ────────────────────────────────────────────────────────

    def _on_heatmap_toggle(self, value):
        if value == "Heatmap":
            if self._heatmap_img is None and self.cover_image:
                self.preview.configure(text="Computing heatmap…")
                threading.Thread(target=self._compute_heatmap, daemon=True).start()
            elif self._heatmap_img:
                self._show_preview_image(self._heatmap_img)
        else:
            if self.image_path:
                ReusableWidgets.load_preview(self.preview, self.image_path, 280)

    def _compute_heatmap(self):
        try:
            hm = LSBEngine.generate_heatmap(self.cover_image)
            self._heatmap_img = hm
            self.ui_queue.put((self._show_preview_image, (hm,)))
        except Exception as exc:
            self.ui_queue.put((
                lambda: self.preview.configure(text=f"Heatmap error: {exc}"), ()))

    def _show_preview_image(self, pil_image):
        try:
            img = pil_image.copy()
            img.thumbnail((280, 280), Image.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
            self.preview.configure(image=ctk_img, text="")
            self.preview._ctk_image = ctk_img
        except Exception:
            pass

    # ── Image browse / drag-drop ──────────────────────────────────────────────

    def on_payload_mode_change(self, _value=None):
        if self.payload_mode.get() == "Text":
            self.file_entry.grid_remove()
            self.file_button.grid_remove()
            self.text_box.grid(row=5, column=0, columnspan=2,
                               sticky="ew", padx=20, pady=(0, 16))
        else:
            self.text_box.grid_remove()
            self.file_entry.grid(row=5, column=0, sticky="ew",
                                  padx=(20, 10), pady=(0, 8))
            self.file_button.grid(row=5, column=1, sticky="e",
                                   padx=(0, 20), pady=(0, 8))
        self.update_capacity_preview()

    def browse_image(self):
        path = filedialog.askopenfilename(
            title="Select Cover Image",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.webp"), ("All", "*.*")],
        )
        if path:
            self.load_image_path(path)

    def load_image_path(self, path):
        try:
            img = Image.open(path)
            self.image_path  = path
            self.cover_image = img
            self._heatmap_img = None
            ReusableWidgets.load_preview(self.preview, path, 280)
            self.heatmap_toggle.set("Original")
            self.heatmap_toggle.grid()
            w, h = img.size
            cap = LSBEngine.capacity_bytes(img)
            self.capacity.update(0, cap)
            self.image_info.configure(
                text=f"{w}×{h} | {img.mode} | {format_bytes(cap)} capacity",
                text_color=COLORS["text_primary"])
            self.suggest_output_path(path)
            self.update_capacity_preview()
        except Exception as exc:
            self.show_error(f"Cannot open image: {exc}")

    def setup_drag_and_drop(self):
        enable_image_drop(
            self.preview,
            on_file=self.load_image_path,
            on_error=self.show_error,
            on_highlight=self.highlight_drop_zone,
        )

    def highlight_drop_zone(self, active):
        color = COLORS["accent"] if active else COLORS["border"]
        self.preview.configure(border_color=color)

    def browse_file(self):
        path = filedialog.askopenfilename(title="Select File to Hide")
        if path:
            self.selected_file = path
            self.file_entry.delete(0, "end")
            self.file_entry.insert(0, path)
            self.update_capacity_preview()

    def choose_output(self):
        carrier = self.carrier_selector.get()
        if carrier == "Audio (WAV)":
            ext, ftypes = ".wav", [("WAV", "*.wav")]
        else:
            ext, ftypes = ".png", [("PNG", "*.png")]
        path = filedialog.asksaveasfilename(
            defaultextension=ext,
            filetypes=ftypes + [("All", "*.*")],
            initialdir=Config.get("last_output_dir"),
        )
        if path:
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, path)

    def suggest_output_path(self, source_path):
        carrier = self.carrier_selector.get()
        ext = ".wav" if carrier == "Audio (WAV)" else ".png"
        base = os.path.splitext(os.path.basename(source_path))[0]
        out_dir = Config.get("last_output_dir") or os.path.dirname(source_path)
        self.output_entry.delete(0, "end")
        self.output_entry.insert(0, os.path.join(out_dir, f"{base}_stego{ext}"))

    def update_password_strength(self):
        pw = self.password_entry.get()
        score = 0
        if len(pw) >= 8:  score += 1
        if len(pw) >= 12: score += 1
        if any(c.isupper() for c in pw) and any(c.islower() for c in pw): score += 1
        if any(c.isdigit() for c in pw): score += 1
        if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in pw): score += 1
        colors = ["#ff5252", "#ff5252", "#ffab40", "#00e676", "#00ffe5"]
        labels = ["Weak", "Weak", "Fair", "Good", "Strong"]
        frac = score / 5
        self.password_strength.set(frac)
        self.password_strength.configure(progress_color=colors[score])
        self.password_strength_label.configure(
            text=f"Password strength: {labels[score]}", text_color=colors[score])

    def update_capacity_preview(self):
        if self.cover_image is None:
            return
        try:
            mode = self.payload_mode.get()
            if mode == "Text":
                msg = self.text_box.get("1.0", "end-1c")
                psize = len(FilePacker.pack_text(msg))
            else:
                psize = os.path.getsize(self.selected_file) if self.selected_file else 0
            cap = max(LSBEngine.capacity_bytes(self.cover_image), 1)
            self.capacity.update(psize, cap)
        except Exception:
            pass

    # ── Encode ────────────────────────────────────────────────────────────────

    def start_encode(self):
        carrier = self.carrier_selector.get()
        password = self.password_entry.get()
        confirm  = self.confirm_entry.get()
        output_path = self.output_entry.get().strip()

        if carrier == "Audio (WAV)":
            if not self.audio_path or not os.path.exists(self.audio_path):
                self.fail_encode_validation("Select a WAV audio file first."); return
        else:
            if self.cover_image is None:
                self.fail_encode_validation("Load a cover image first."); return

        if not password:
            self.fail_encode_validation("Enter a password."); return
        if password != confirm:
            self.fail_encode_validation("Passwords do not match."); return
        if not output_path:
            self.fail_encode_validation("Choose an output path."); return

        try:
            payload = self.build_payload()
        except (ValueError, OSError) as exc:
            self.fail_encode_validation(str(exc)); return

        if carrier == "Image (LSB)":
            cap = max(FilePacker.max_file_size_for_image(self.cover_image), 0)
            if cap < len(payload):
                self.fail_encode_validation(
                    f"Image too small. Need {len(payload)/1024:.1f}kb, "
                    f"have {cap/1024:.1f}kb."); return

        description = self.encode_description(output_path, len(payload))
        image_copy  = self.cover_image.copy() if self.cover_image else None
        self.set_busy(True, "Encoding payload…")
        threading.Thread(
            target=self.encode_worker,
            args=(image_copy, payload, password, output_path,
                  description, carrier),
            daemon=True,
        ).start()

    def build_payload(self):
        seal     = self.seal_switch.get()
        destruct = self.destruct_switch.get()
        password = self.password_entry.get()
        is_text  = self.payload_mode.get() == "Text"

        if is_text:
            msg = self.text_box.get("1.0", "end-1c")
            if not msg:
                raise ValueError("Enter text to hide.")
            if seal:
                return FilePacker.pack_text_sealed(msg, password)
            if destruct:
                return FilePacker.pack_text_self_destruct(msg)
            return FilePacker.pack_text(msg)
        else:
            if not self.selected_file:
                raise ValueError("Choose a file to hide.")
            if seal:
                return FilePacker.pack_file_sealed(self.selected_file, password)
            if destruct:
                return FilePacker.pack_file_self_destruct(self.selected_file)
            return FilePacker.pack_file(self.selected_file)

    def encode_description(self, output_path, payload_size):
        out = os.path.basename(output_path)
        if self.payload_mode.get() == "Text":
            return f"Encoded text ({payload_size} bytes) into {out}"
        fname = os.path.basename(self.selected_file) if self.selected_file else "file"
        return f"Encoded file '{fname}' ({payload_size} bytes) into {out}"

    def encode_worker(self, image, payload, password, output_path, description, carrier):
        start_time = time.perf_counter()
        original_copy = image.copy() if image is not None else None
        try:
            encrypted = CryptoEngine.encrypt(payload, password)

            if carrier == "Audio (WAV)":
                AudioEngine.encode(self.audio_path, encrypted, output_path)
                used_pct = 0.0
                stego_img = None
            elif carrier == "PNG Metadata":
                PngChunkEngine.encode(self.image_path, encrypted, output_path)
                used_pct = 0.0
                stego_img = None
            else:
                # Image (LSB) — adaptive or standard
                if self.adaptive_switch.get():
                    stego_img = LSBEngine.encode_adaptive(image, encrypted)
                else:
                    stego_img = LSBEngine.encode(image, encrypted)
                stego_img.save(output_path, "PNG")
                used_pct = LSBEngine.bits_used_percent(image, len(encrypted))

            # Steganalysis score (image LSB only)
            steg_score = None
            if carrier == "Image (LSB)" and stego_img is not None and original_copy is not None:
                try:
                    steg_score = LSBEngine.steganalysis_score(original_copy, stego_img)
                except Exception:
                    pass

            duration_ms = (time.perf_counter() - start_time) * 1000
            self.log_operation("encode", image, len(payload), True, "", duration_ms)
            self.ui_queue.put((
                self.on_encode_success,
                (output_path, len(payload), used_pct, duration_ms, description, steg_score),
            ))
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            reason = str(exc)
            self.log_operation("encode", image, len(payload), False, reason, duration_ms)
            self.ui_queue.put((self.on_encode_failure, (reason, duration_ms, description)))

    # ── UI queue ──────────────────────────────────────────────────────────────

    def process_ui_queue(self):
        while True:
            try:
                callback, args = self.ui_queue.get_nowait()
            except queue.Empty:
                break
            if callable(callback):
                callback(*args)
        self.after(100, self.process_ui_queue)

    def on_encode_success(self, output_path, payload_size, used_percent,
                          duration_ms, description, steg_score=None):
        self.set_busy(False, "Encoding complete.")
        details = (f"{output_path}\n"
                   f"Payload: {format_bytes(payload_size)} | Capacity used: {used_percent:.2f}%")
        self.success_details.configure(text=details)

        if steg_score is not None:
            if steg_score < 0.1:
                sc, sl = COLORS["accent"],    f"Detectability: {steg_score:.2f} — Low Risk ✓"
            elif steg_score < 0.3:
                sc, sl = COLORS["warning"],   f"Detectability: {steg_score:.2f} — Medium Risk"
            else:
                sc, sl = COLORS["error"],     f"Detectability: {steg_score:.2f} — High Risk (use larger image)"
            self.steg_score_label.configure(text=sl, text_color=sc)
            self.steg_score_bar.configure(progress_color=sc)
            self.steg_score_bar.set(min(steg_score, 1.0))
            self.steg_score_label.grid()
            self.steg_score_bar.grid()
        else:
            self.steg_score_label.grid_remove()
            self.steg_score_bar.grid_remove()

        self.success_card.grid()
        Config.set("last_output_dir", os.path.dirname(os.path.abspath(output_path)))
        self.add_history("encode", description, True, duration_ms)
        if self.on_encode_complete:
            self.on_encode_complete(output_path)
        self._notify_status("Ready")

    def on_encode_failure(self, reason, duration_ms, description):
        self.show_error(reason)
        self.add_history("encode", description, False, duration_ms, reason)

    def fail_encode_validation(self, reason):
        self.show_error(reason)
        self.log_operation("encode", self.cover_image, 0, False, reason, 0)
        self.add_history("encode", "Encode blocked", False, 0, reason)

    def log_operation(self, operation, image, payload_size, success, reason, duration_ms):
        dimensions = f"{image.width}x{image.height}" if image else "unknown"
        self.logger.info(
            "operation=%s timestamp=%s image_dimensions=%s payload_size=%s "
            "success=%s reason=%s duration_ms=%.0f",
            operation, datetime.now().isoformat(timespec="seconds"),
            dimensions, payload_size, success, reason or "-", duration_ms,
        )

    def add_history(self, op_type, description, success, duration_ms, reason=""):
        if self.history_callback:
            self.history_callback(op_type, description, success, duration_ms, reason)

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
