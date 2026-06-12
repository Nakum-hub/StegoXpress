"""
ShieldTab — StegoShield: N-of-K secret sharing across multiple images.
Any K of the N stego images can reconstruct the original secret.
"""
import os
import queue
import threading
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image

from core.file_packer import FilePacker
from core.shield_engine import ShieldEngine
from gui.widgets import COLORS, ReusableWidgets as W


class ShieldTab(ctk.CTkFrame):
    def __init__(self, parent, status_callback=None, history_callback=None):
        super().__init__(parent, fg_color="transparent")
        self._status_cb  = status_callback  or (lambda *a, **k: None)
        self._history_cb = history_callback or (lambda *a, **k: None)
        self._ui_queue   = queue.Queue()
        self._cover_paths: list = []
        self._recon_paths: list = []
        self._build_ui()
        self._poll_queue()

    # ── Build ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.columnconfigure(0, weight=1)

        # ── TOP: Encode card ──
        enc_card = W.card(self)
        enc_card.grid(row=0, column=0, padx=12, pady=(12, 6), sticky="ew")
        enc_card.columnconfigure((0, 1, 2, 3), weight=1)

        W.label(enc_card, "SPLIT SECRET ACROSS IMAGES", size=11, muted=True).grid(
            row=0, column=0, columnspan=4, padx=14, pady=(12, 4), sticky="w")

        # N / K sliders
        slider_frame = ctk.CTkFrame(enc_card, fg_color="transparent")
        slider_frame.grid(row=1, column=0, columnspan=4, padx=14, pady=(0, 8), sticky="ew")
        slider_frame.columnconfigure((0, 1), weight=1)

        nk_left = ctk.CTkFrame(slider_frame, fg_color="transparent")
        nk_left.grid(row=0, column=0, padx=(0, 12), sticky="ew")
        W.label(nk_left, "Total shares (N):", size=12).pack(anchor="w")
        self._n_label = W.label(nk_left, "N = 5", size=13)
        self._n_label.pack(anchor="w")
        self._n_slider = ctk.CTkSlider(nk_left, from_=2, to=10, number_of_steps=8,
                                        fg_color=COLORS["border"],
                                        progress_color=COLORS["accent"],
                                        button_color=COLORS["accent"],
                                        command=self._on_n_change)
        self._n_slider.set(5)
        self._n_slider.pack(fill="x", pady=(4, 0))

        nk_right = ctk.CTkFrame(slider_frame, fg_color="transparent")
        nk_right.grid(row=0, column=1, sticky="ew")
        W.label(nk_right, "Minimum shares to decode (K):", size=12).pack(anchor="w")
        self._k_label = W.label(nk_right, "K = 3 — any 3 of 5 images reconstruct the secret", size=12)
        self._k_label.pack(anchor="w")
        self._k_slider = ctk.CTkSlider(nk_right, from_=2, to=5, number_of_steps=3,
                                        fg_color=COLORS["border"],
                                        progress_color=COLORS["accent_dim"],
                                        button_color=COLORS["accent_dim"],
                                        command=self._on_k_change)
        self._k_slider.set(3)
        self._k_slider.pack(fill="x", pady=(4, 0))

        # Cover image grid
        W.label(enc_card, "COVER IMAGES", size=11, muted=True).grid(
            row=2, column=0, columnspan=4, padx=14, pady=(8, 4), sticky="w")

        self._covers_frame = ctk.CTkFrame(enc_card, fg_color="transparent")
        self._covers_frame.grid(row=3, column=0, columnspan=4, padx=14, pady=(0, 8), sticky="ew")
        self._refresh_cover_rows(5)

        # Payload
        W.label(enc_card, "SECRET MESSAGE", size=11, muted=True).grid(
            row=4, column=0, columnspan=4, padx=14, pady=(4, 4), sticky="w")
        self._payload_box = ctk.CTkTextbox(enc_card, height=70, fg_color=COLORS["surface"],
                                            text_color=COLORS["text_primary"],
                                            border_color=COLORS["border"], border_width=1)
        self._payload_box.grid(row=5, column=0, columnspan=4, padx=14, pady=(0, 8), sticky="ew")

        # Password + output + action
        pw_row = ctk.CTkFrame(enc_card, fg_color="transparent")
        pw_row.grid(row=6, column=0, columnspan=4, padx=14, pady=(0, 8), sticky="ew")
        pw_row.columnconfigure((0, 1, 2, 3), weight=1)

        W.label(pw_row, "Password:", size=12).grid(row=0, column=0, padx=(0, 6), sticky="e")
        self._enc_pass = W.entry(pw_row, "Encryption password", show="•")
        self._enc_pass.grid(row=0, column=1, padx=6, sticky="ew")
        W.label(pw_row, "Output dir:", size=12).grid(row=0, column=2, padx=6, sticky="e")
        self._out_dir = W.entry(pw_row, "Output directory")
        self._out_dir.grid(row=0, column=3, padx=(6, 0), sticky="ew")
        W.ghost_button(pw_row, "...", self._browse_outdir, width=36).grid(row=0, column=4, padx=(4, 0))

        action_row = ctk.CTkFrame(enc_card, fg_color="transparent")
        action_row.grid(row=7, column=0, columnspan=4, pady=(0, 12))
        W.primary_button(action_row, "SPLIT & ENCODE", self._start_encode).pack(side="left", padx=8)
        self._enc_status = W.label(action_row, "", size=12)
        self._enc_status.pack(side="left", padx=8)

        # ── BOTTOM: Reconstruct card ──
        rec_card = W.card(self)
        rec_card.grid(row=1, column=0, padx=12, pady=(6, 12), sticky="ew")
        rec_card.columnconfigure(0, weight=1)

        W.label(rec_card, "RECONSTRUCT FROM SHARES", size=11, muted=True).grid(
            row=0, column=0, padx=14, pady=(12, 4), sticky="w")

        self._recon_frame = ctk.CTkFrame(rec_card, fg_color="transparent")
        self._recon_frame.grid(row=1, column=0, padx=14, pady=(0, 8), sticky="ew")
        W.ghost_button(rec_card, "+ Add Share Image", self._add_recon_row).grid(
            row=2, column=0, padx=14, pady=(0, 4), sticky="w")

        rec_pw_row = ctk.CTkFrame(rec_card, fg_color="transparent")
        rec_pw_row.grid(row=3, column=0, padx=14, pady=(4, 8), sticky="ew")
        rec_pw_row.columnconfigure(1, weight=1)
        W.label(rec_pw_row, "Password:", size=12).grid(row=0, column=0, padx=(0, 8))
        self._rec_pass = W.entry(rec_pw_row, "Decryption password", show="•")
        self._rec_pass.grid(row=0, column=1, sticky="ew")
        W.primary_button(rec_pw_row, "RECONSTRUCT", self._start_reconstruct, width=160).grid(
            row=0, column=2, padx=(12, 0))

        self._rec_result = ctk.CTkTextbox(rec_card, height=80, state="disabled",
                                           fg_color=COLORS["surface"],
                                           text_color=COLORS["text_primary"],
                                           border_color=COLORS["border"], border_width=1)
        self._rec_result.grid(row=4, column=0, padx=14, pady=(0, 12), sticky="ew")

    # ── Dynamic rows ─────────────────────────────────────────────────────────

    def _refresh_cover_rows(self, n):
        for w in self._covers_frame.winfo_children():
            w.destroy()
        self._cover_paths = [""] * n
        self._covers_frame.columnconfigure(list(range(n)), weight=1)
        for i in range(n):
            col = ctk.CTkFrame(self._covers_frame, fg_color="transparent")
            col.grid(row=0, column=i, padx=4, sticky="nsew")
            lbl = W.label(col, f"Share {i + 1}", size=11, muted=True)
            lbl.pack()
            prev = ctk.CTkLabel(col, text="No image", width=80, height=80,
                                 fg_color=COLORS["card"],
                                 text_color=COLORS["text_muted"],
                                 corner_radius=6)
            prev.pack(pady=2)
            W.ghost_button(col, "Browse", lambda idx=i, p=prev: self._browse_cover(idx, p),
                           width=80).pack(pady=2)

    def _browse_cover(self, idx, preview_widget):
        path = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg"), ("All", "*.*")]
        )
        if path:
            self._cover_paths[idx] = path
            try:
                W.load_preview(preview_widget, path, 80)
            except Exception:
                preview_widget.configure(text=os.path.basename(path)[:10])

    def _add_recon_row(self):
        idx = len(self._recon_paths)
        self._recon_paths.append("")
        row = ctk.CTkFrame(self._recon_frame, fg_color="transparent")
        row.columnconfigure(1, weight=1)
        row.pack(fill="x", pady=2)
        W.label(row, f"Share {idx + 1}:", size=12).grid(row=0, column=0, padx=(0, 8))
        ent = W.entry(row, "Path to share image...")
        ent.grid(row=0, column=1, sticky="ew", padx=(0, 6))

        def pick(e=ent, i=idx):
            p = filedialog.askopenfilename(
                filetypes=[("Images", "*.png *.jpg *.jpeg"), ("All", "*.*")]
            )
            if p:
                self._recon_paths[i] = p
                e.delete(0, "end"); e.insert(0, p)

        W.ghost_button(row, "Browse", pick, width=70).grid(row=0, column=2)

    def _browse_outdir(self):
        d = filedialog.askdirectory()
        if d:
            self._out_dir.delete(0, "end")
            self._out_dir.insert(0, d)

    # ── Slider callbacks ──────────────────────────────────────────────────────

    def _on_n_change(self, val):
        n = int(round(val))
        self._n_label.configure(text=f"N = {n}")
        k = int(round(self._k_slider.get()))
        self._k_slider.configure(to=n)
        if k > n:
            self._k_slider.set(n)
            k = n
        self._k_label.configure(
            text=f"K = {k} — any {k} of {n} images reconstruct the secret")
        self._refresh_cover_rows(n)

    def _on_k_change(self, val):
        k = int(round(val))
        n = int(round(self._n_slider.get()))
        self._k_label.configure(
            text=f"K = {k} — any {k} of {n} images reconstruct the secret")

    # ── Encode / reconstruct workers ─────────────────────────────────────────

    def _start_encode(self):
        n = int(round(self._n_slider.get()))
        k = int(round(self._k_slider.get()))
        missing = [i + 1 for i, p in enumerate(self._cover_paths) if not p or not os.path.exists(p)]
        if missing:
            self._enc_status.configure(
                text=f"Missing cover image(s): {missing}", text_color=COLORS["error"]); return
        msg = self._payload_box.get("1.0", "end").strip()
        if not msg:
            self._enc_status.configure(text="Enter a secret message.", text_color=COLORS["error"]); return
        pw = self._enc_pass.get()
        if not pw:
            self._enc_status.configure(text="Enter a password.", text_color=COLORS["error"]); return
        out_dir = self._out_dir.get().strip() or os.path.expanduser("~")
        self._enc_status.configure(text="Encoding…", text_color=COLORS["text_muted"])
        threading.Thread(
            target=self._encode_worker,
            args=(self._cover_paths[:n], msg, pw, n, k, out_dir),
            daemon=True
        ).start()

    def _encode_worker(self, cover_paths, msg, pw, n, k, out_dir):
        try:
            covers = [Image.open(p) for p in cover_paths]
            packed = FilePacker.pack_text(msg)
            stegos = ShieldEngine.encode_shares(packed, covers, pw, n, k)
            saved = []
            for i, img in enumerate(stegos):
                fname = os.path.join(out_dir, f"shield_share_{i + 1}.png")
                img.save(fname, "PNG")
                saved.append(fname)
            self._ui_queue.put(("encode_ok", saved, n, k))
        except Exception as exc:
            self._ui_queue.put(("error", str(exc)))

    def _start_reconstruct(self):
        loaded = [(i + 1, p) for i, p in enumerate(self._recon_paths) if p and os.path.exists(p)]
        if not loaded:
            self._show_recon("Add at least one share image.", COLORS["error"]); return
        pw = self._rec_pass.get()
        if not pw:
            self._show_recon("Enter the decryption password.", COLORS["error"]); return
        threading.Thread(
            target=self._recon_worker, args=(loaded, pw), daemon=True
        ).start()

    def _recon_worker(self, loaded_paths, pw):
        try:
            shares = [(idx, Image.open(p)) for idx, p in loaded_paths]
            raw = ShieldEngine.decode_shares(shares, pw)
            result = FilePacker.unpack(raw)
            self._ui_queue.put(("recon_ok", result))
        except Exception as exc:
            self._ui_queue.put(("error_recon", str(exc)))

    # ── UI helpers ────────────────────────────────────────────────────────────

    def _show_recon(self, text, color=None):
        self._rec_result.configure(state="normal")
        self._rec_result.delete("1.0", "end")
        self._rec_result.insert("1.0", text)
        self._rec_result.configure(state="disabled",
                                   text_color=color or COLORS["text_primary"])

    def _poll_queue(self):
        try:
            while True:
                msg = self._ui_queue.get_nowait()
                if msg[0] == "encode_ok":
                    _, saved, n, k = msg
                    self._enc_status.configure(
                        text=f"✓ {n} shares saved. Any {k} reconstruct the secret.",
                        text_color=COLORS["accent"])
                    self._history_cb("shield", f"Shield split {n}-of-{k} → {len(saved)} files", True, 0)
                elif msg[0] == "recon_ok":
                    result = msg[1]
                    text = result.get("text", f"[file: {result.get('filename','?')}]")
                    self._show_recon(text)
                    self._history_cb("shield", "Shield reconstruction successful", True, 0)
                elif msg[0] == "error":
                    self._enc_status.configure(text=f"✗ {msg[1]}", text_color=COLORS["error"])
                elif msg[0] == "error_recon":
                    self._show_recon(f"Failed: {msg[1]}", COLORS["error"])
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)
