"""
VaultEngine — dual-password hidden volumes.
First 50% of pixel capacity = outer (decoy) zone.
Second 50% = inner (real) zone.

NOTE (audit finding V4): plausible deniability here is statistical, not absolute.
A forensic analyst can observe LSB randomness across the WHOLE image while the
decoy only "explains" the first half. Treat the decoy as protection against a
casual adversary, not a nation-state. See SECURITY.md for the honest threat model.

v2.1: Rewrote pixel I/O to use NumPy instead of the deprecated Image.getdata() /
Image.putdata() API (removed in Pillow 14, 2027-10-15). Behaviour is identical.
"""
import struct

import numpy as np
from PIL import Image

from core.crypto_engine import CryptoEngine
from core.lsb_engine import LSBEngine


class VaultEngine:
    @staticmethod
    def encode(image: Image.Image, decoy_payload: bytes, real_payload: bytes,
               password_outer: str, password_real: str) -> Image.Image:
        working = LSBEngine._to_rgb_image(image)
        arr = np.asarray(working, dtype=np.uint8).reshape(-1, 3).copy()
        total_pix = arr.shape[0]
        split_pix = total_pix // 2

        enc_outer = CryptoEngine.encrypt(decoy_payload, password_outer)
        enc_inner = CryptoEngine.encrypt(real_payload, password_real)

        cap_outer = split_pix * 3 // 8 - 4
        cap_inner = (total_pix - split_pix) * 3 // 8 - 4
        if len(enc_outer) > cap_outer:
            raise ValueError(f"Decoy payload too large: needs {len(enc_outer)} bytes, "
                             f"outer zone holds {cap_outer} bytes")
        if len(enc_inner) > cap_inner:
            raise ValueError(f"Real payload too large: needs {len(enc_inner)} bytes, "
                             f"inner zone holds {cap_inner} bytes")

        VaultEngine._write_zone_arr(arr, 0, split_pix, enc_outer)
        VaultEngine._write_zone_arr(arr, split_pix, total_pix, enc_inner)

        out = Image.fromarray(arr.reshape(working.height, working.width, 3), "RGB")
        return out

    @staticmethod
    def decode_outer(image: Image.Image, password_outer: str) -> bytes:
        working = LSBEngine._to_rgb_image(image)
        arr = np.asarray(working, dtype=np.uint8).reshape(-1, 3)
        total_pix = arr.shape[0]
        split_pix = total_pix // 2
        enc = VaultEngine._read_zone_arr(arr, 0, split_pix)
        try:
            return CryptoEngine.decrypt(enc, password_outer)
        except ValueError as exc:
            raise ValueError("Wrong password for outer vault") from exc

    @staticmethod
    def decode_inner(image: Image.Image, password_real: str) -> bytes:
        working = LSBEngine._to_rgb_image(image)
        arr = np.asarray(working, dtype=np.uint8).reshape(-1, 3)
        total_pix = arr.shape[0]
        split_pix = total_pix // 2
        enc = VaultEngine._read_zone_arr(arr, split_pix, total_pix)
        try:
            return CryptoEngine.decrypt(enc, password_real)
        except ValueError as exc:
            raise ValueError("Wrong password for inner vault") from exc

    @staticmethod
    def capacity_outer_bytes(image: Image.Image) -> int:
        total_pix = image.width * image.height
        split_pix = total_pix // 2
        return split_pix * 3 // 8 - 4

    @staticmethod
    def capacity_inner_bytes(image: Image.Image) -> int:
        total_pix = image.width * image.height
        split_pix = total_pix // 2
        return (total_pix - split_pix) * 3 // 8 - 4

    # ── NumPy zone helpers ──
    @staticmethod
    def _write_zone_arr(arr: np.ndarray, start: int, end: int, payload: bytes) -> None:
        full = struct.pack(">I", len(payload)) + payload
        bits = np.unpackbits(np.frombuffer(full, dtype=np.uint8))
        zone = arr[start:end].reshape(-1)
        n = min(bits.size, zone.size)
        zone[:n] = (zone[:n] & 0xFE) | bits[:n]
        arr[start:end] = zone.reshape(-1, 3)

    @staticmethod
    def _read_zone_arr(arr: np.ndarray, start: int, end: int) -> bytes:
        zone_flat = arr[start:end].reshape(-1)
        lsb = (zone_flat & 1).astype(np.uint8)
        if lsb.size < 32:
            raise ValueError("Zone too small to hold a length header")
        length = int(np.packbits(lsb[:32]).view(">u4")[0])
        need = 32 + length * 8
        if need > lsb.size:
            raise ValueError("Zone too small for stored payload length")
        return np.packbits(lsb[32:need]).tobytes()
