"""
VaultTab — StegoVault: dual-password hidden volumes.
Decoy password reveals harmless content; real password reveals the actual secret.

Note (audit V4): the inner volume is a best-effort plausible-deniability
feature, not a proven hidden-volume scheme. See SECURITY.md for the threat
model and limitations.
"""
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image

from core.crypto_engine import CryptoEngine
from core.file_packer import FilePacker
from core.vault_engine import VaultEngine
from gui.widgets import COLORS, ReusableWidgets as W


class VaultTab(ctk.CTkFrame):
    def __init__(self, parent, status_callback=None, history_callback=None):
        super().__init__(parent, fg_color="transparent")
        self._status_cb = status_callback or (lambda msg, color=None: None)
        self._history_cb = history_callback or (lambda *a, **k: None)
        self._ui_queue = queue.Queue()
        self._cover_image_path = None
        self._cover_image = None
        self._stego_path = None
        self._build_ui()
        self._poll_queue()

    # ── Build ────────────────────────────────────────────────────────

    def _build_ui(self):
        self.columnconfigure((0, 1, 2), weight=1, uniform="col")
        self.rowconfigure(0, weight=1)

        # ── LEFT: Cover image ──
        left = W.card(self)
        left.grid(row=0, column=0, padx=(12, 6), pady=12, sticky="nsew")
        left.columnconfigure(0, weight=1)

        W.label(left, "COVER IMAGE", size=11, muted=True).pack(pady=(14, 6), padx=14, anchor="w")
        self._preview = W.image_preview(left)
        self._preview.pack(padx=14, pady=(0, 8))
        W.ghost_button(left, "Browse Image", self._browse_cover).pack(padx=14, pady=(0, 4))

        W.label(left, "Outer zone (decoy):", size=11, muted=True).pack(padx=14, anchor="w")
        self._cap_outer = W.capacity_bar(left)
        self._cap_outer.pack(padx=14, pady=(0, 6), fill="x")
        W.label(left, "Inner zone (real):", size=11, muted=True).pack(padx=14, anchor="w")
        self._cap_inner = W.capacity_bar(left)
        self._cap_inner.pack(padx=14, pady=(0, 14), fill="x")

        # ── MIDDLE: Payload ──
        mid = W.card(self)
        mid.grid(row=0, column=1, padx=6, pady=12, sticky="nsew")
        mid.columnconfigure(0, weight=1)

        W.label(mid, "DECOY MESSAGE", size=11, muted=True).pack(pady=(14, 4), padx=14, anchor="w")
        W.label(mid, "Shown if forced to reveal password", size=10, muted=True).pack(padx=14, anchor="w")
        self._decoy_box = ctk.CTkTextbox(mid, height=90, fg_color=COLORS["surface"],
                                         text_color=COLORS["text_primary"],
                                         border_color=COLORS["border"], border_width=1,
                                         font=ctk.CTkFont(family="JetBrains Mono", size=12))
        self._decoy_box.pack(padx=14, pady=(4, 12), fill="x")

        W.label(mid, "REAL MESSAGE", size=11, muted=True).pack(padx=14, anchor="w")
        W.label(mid, "Never revealed under duress", size=10, muted=True).pack(padx=14, anchor="w")
        self._real_box = ctk.CTkTextbox(mid, height=90, fg_color=COLORS["surface"],
                                        text_color=COLORS["text_primary"],
                                        border_color=COLORS["border"], border_width=1,
                                        font=ctk.CTkFont(family="JetBrains Mono", size=12))
        self._real_box.pack(padx=14, pady=(4, 14), fill="x")

        note = ctk.CTkLabel(mid,
                            text="\u26a0 Never use the same password for decoy and real.",
                            text_color=COLORS["warning"], font=ctk.CTkFont(size=11))
        note.pack(padx=14, pady=(0, 14))

        # ── RIGHT: Passwords + output ──
        right = W.card(self)
        right.grid(row=0, column=2, padx=(6, 12), pady=12, sticky="nsew")
        right.columnconfigure(0, weight=1)

        W.label(right, "PASSWORDS", size=11, muted=True).pack(pady=(14, 4), padx=14, anchor="w")

        W.label(right, "Decoy Password", size=12).pack(padx=14, anchor="w")
        self._decoy_pass = W.entry(right, "Decoy password", show="\u2022")
        self._decoy_pass.pack(padx=14, pady=(2, 2), fill="x")
        self._decoy_confirm = W.entry(right, "Confirm decoy password", show="\u2022")
        self._decoy_confirm.pack(padx=14, pady=(0, 8), fill="x")

        W.label(right, "Real Password", size=12).pack(padx=14, anchor="w")
        self._real_pass = W.entry(right, "Real password", show="\u2022")
        self._real_pass.pack(padx=14, pady=(2, 2), fill="x")
        self._real_confirm = W.entry(right, "Confirm real password", show="\u2022")
        self._real_confirm.pack(padx=14, pady=(0, 8), fill="x")

        W.label(right, "OUTPUT", size=11, muted=True).pack(padx=14, anchor="w")
        out_row = ctk.CTkFrame(right, fg_color="transparent")
        out_row.columnconfigure(0, weight=1)
        out_row.pack(padx=14, pady=(4, 8), fill="x")
        self._out_entry = W.entry(out_row, "vault_output.png")
        self._out_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        W.ghost_button(out_row, "...", self._browse_output, width=40).grid(row=0, column=1)

        W.primary_button(right, "CREATE VAULT IMAGE", self._start_encode).pack(pady=(8, 6))
        self._encode_status = W.label(right, "", size=12)
        self._encode_status.pack(padx=14, pady=(0, 14))

        # ── DECODE section ──
        decode_card = W.card(self)
        decode_card.grid(row=1, column=0, columnspan=3, padx=12, pady=(0, 12), sticky="ew")
        decode_card.columnconfigure((0, 1, 2, 3, 4), weight=1)

        W.label(decode_card, "DECODE VAULT IMAGE", size=11, muted=True).grid(
            row=0, column=0, columnspan=5, padx=14, pady=(12, 6), sticky="w")

        W.label(decode_card, "Stego Image:", size=12).grid(row=1, column=0, padx=(14, 4), sticky="e")
        self._decode_img_entry = W.entry(decode_card, "Path to vault image...")
        self._decode_img_entry.grid(row=1, column=1, columnspan=2, padx=4, sticky="ew")
        W.ghost_button(decode_card, "Browse", self._browse_stego, width=80).grid(row=1, column=3, padx=4)

        W.label(decode_card, "Password:", size=12).grid(row=2, column=0, padx=(14, 4), pady=8, sticky="e")
        self._decode_pass = W.entry(decode_card, "Enter either password", show="\u2022")
        self._decode_pass.grid(row=2, column=1, columnspan=2, padx=4, pady=8, sticky="ew")
        W.primary_button(decode_card, "DECODE", self._start_decode, width=120).grid(
            row=2, column=3, padx=4, pady=8)

        self._decode_result = ctk.CTkTextbox(decode_card, height=70, state="disabled",
                                             fg_color=COLORS["surface"],
                                             text_color=COLORS["text_primary"],
                                             border_color=COLORS["border"], border_width=1)
        self._decode_result.grid(row=3, column=0, columnspan=5, padx=14, pady=(0, 12), sticky="ew")
        self._decode_type_label = W.label(decode_card, "", size=12)
        self._decode_type_label.grid(row=4, column=0, columnspan=5, padx=14, pady=(0, 12))

    # ── Browse helpers ────────────────────────────────────────────────

    def _browse_cover(self):
        path = filedialog.askopenfilename(
            title="Select Cover Image",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp"), ("All", "*.*")]
        )
        if not path:
            return
        self._cover_image_path = path
        try:
            self._cover_image = Image.open(path)
            W.load_preview(self._preview, path, 200)
            cap_o = VaultEngine.capacity_outer_bytes(self._cover_image)
            cap_i = VaultEngine.capacity_inner_bytes(self._cover_image)
            self._cap_outer.update(0, cap_o)
            self._cap_inner.update(0, cap_i)
            base = os.path.splitext(os.path.basename(path))[0]
            outdir = os.path.dirname(path)
            self._out_entry.delete(0, "end")
            self._out_entry.insert(0, os.path.join(outdir, f"{base}_vault.png"))
        except Exception as exc:
            self._encode_status.configure(text=f"Error: {exc}", text_color=COLORS["error"])

    def _browse_output(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".png", filetypes=[("PNG", "*.png")]
        )
        if path:
            self._out_entry.delete(0, "end")
            self._out_entry.insert(0, path)

    def _browse_stego(self):
        path = filedialog.askopenfilename(
            title="Select Vault Image",
            filetypes=[("Images", "*.png *.jpg *.jpeg"), ("All", "*.*")]
        )
        if path:
            self._decode_img_entry.delete(0, "end")
            self._decode_img_entry.insert(0, path)

    # ── Encode ────────────────────────────────────────────────────────────

    def _start_encode(self):
        if not self._cover_image_path:
            self._set_status("Select a cover image first.", COLORS["error"])
            return
        decoy_msg = self._decoy_box.get("1.0", "end").strip()
        real_msg = self._real_box.get("1.0", "end").strip()
        decoy_pw = self._decoy_pass.get()
        decoy_conf = self._decoy_confirm.get()
        real_pw = self._real_pass.get()
        real_conf = self._real_confirm.get()
        out_path = self._out_entry.get().strip()

        if decoy_pw != decoy_conf:
            self._set_status("Decoy passwords do not match.", COLORS["error"])
            return
        if real_pw != real_conf:
            self._set_status("Real passwords do not match.", COLORS["error"])
            return
        if decoy_pw == real_pw:
            self._set_status("Decoy and real passwords must differ.", COLORS["error"])
            return
        if not decoy_pw or not real_pw:
            self._set_status("Both passwords required.", COLORS["error"])
            return
        if not out_path:
            self._set_status("Set an output path.", COLORS["error"])
            return

        self._set_status("Creating vault\u2026", COLORS["text_muted"])
        threading.Thread(
            target=self._encode_worker,
            args=(decoy_msg, real_msg, decoy_pw, real_pw, out_path),
            daemon=True
        ).start()

    def _encode_worker(self, decoy_msg, real_msg, decoy_pw, real_pw, out_path):
        try:
            cover = Image.open(self._cover_image_path)
            outer, inner = FilePacker.pack_vault(decoy_msg, real_msg)
            stego = VaultEngine.encode(cover, outer, inner, decoy_pw, real_pw)
            stego.save(out_path, "PNG")
            self._ui_queue.put(("encode_ok", out_path))
        except Exception as exc:
            self._ui_queue.put(("error", str(exc)))

    # ── Decode ────────────────────────────────────────────────────────────

    def _start_decode(self):
        img_path = self._decode_img_entry.get().strip()
        password = self._decode_pass.get()
        if not img_path or not os.path.exists(img_path):
            self._set_decode_result("Image not found.", COLORS["error"])
            return
        if not password:
            self._set_decode_result("Enter a password.", COLORS["error"])
            return
        threading.Thread(
            target=self._decode_worker, args=(img_path, password), daemon=True
        ).start()

    def _decode_worker(self, img_path, password):
        try:
            image = Image.open(img_path)
            # Try outer first
            for decode_fn, label in [
                (lambda i, p: VaultEngine.decode_outer(i, p), "outer"),
                (lambda i, p: VaultEngine.decode_inner(i, p), "inner"),
            ]:
                try:
                    raw = decode_fn(image, password)
                    result = FilePacker.unpack(raw)
                    self._ui_queue.put(("decode_ok", result, label))
                    return
                except ValueError:
                    continue
            self._ui_queue.put(("error", "Wrong password or not a vault image."))
        except Exception as exc:
            self._ui_queue.put(("error", str(exc)))

    # ── UI helpers ──────────────────────────────────────────────────────────

    def _set_status(self, msg, color=None):
        self._encode_status.configure(
            text=msg, text_color=color or COLORS["text_primary"]
        )

    def _set_decode_result(self, text, color=None):
        self._decode_result.configure(state="normal")
        self._decode_result.delete("1.0", "end")
        self._decode_result.insert("1.0", text)
        self._decode_result.configure(state="disabled")
        if color:
            self._decode_type_label.configure(text="", text_color=color)

    def _poll_queue(self):
        try:
            while True:
                msg = self._ui_queue.get_nowait()
                if msg[0] == "encode_ok":
                    self._set_status(f"\u2713 Vault saved: {os.path.basename(msg[1])}", COLORS["accent"])
                    self._history_cb("vault", f"Vault image created \u2192 {os.path.basename(msg[1])}", True, 0)
                elif msg[0] == "decode_ok":
                    result, zone = msg[1], msg[2]
                    text = result.get("text", f"[binary file: {result.get('filename', '?')}]")
                    self._set_decode_result(text)
                    if zone == "inner":
                        lbl, col = "\U0001f510 REAL MESSAGE \u2014 inner vault", COLORS["accent"]
                    else:
                        lbl, col = "\U0001f3ad DECOY MESSAGE \u2014 outer vault", COLORS["text_muted"]
                    self._decode_type_label.configure(text=lbl, text_color=col)
                    self._history_cb("vault", f"Decoded {zone} vault message", True, 0)
                elif msg[0] == "error":
                    self._set_status(f"\u2717 {msg[1]}", COLORS["error"])
                    self._set_decode_result(f"Failed: {msg[1]}", COLORS["error"])
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)
