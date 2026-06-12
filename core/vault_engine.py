"""
VaultEngine — dual-password hidden volumes.
First 50% of pixel capacity = outer (decoy) zone.
Second 50% = inner (real) zone.

NOTE (audit finding V4): plausible deniability here is statistical, not absolute.
A forensic analyst can observe LSB randomness across the WHOLE image while the
decoy only "explains" the first half. Treat the decoy as protection against a
casual adversary, not a nation-state. See SECURITY.md for the honest threat model.
"""
import struct
from PIL import Image
from core.lsb_engine import LSBEngine
from core.crypto_engine import CryptoEngine


class VaultEngine:
    @staticmethod
    def encode(image: Image.Image, decoy_payload: bytes, real_payload: bytes,
               password_outer: str, password_real: str) -> Image.Image:
        working = LSBEngine._to_rgb_image(image)
        total_pix = working.width * working.height
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

        pix = list(working.getdata())
        VaultEngine._write_zone(pix, 0, split_pix, enc_outer)
        VaultEngine._write_zone(pix, split_pix, total_pix, enc_inner)
        out = Image.new("RGB", working.size)
        out.putdata(pix)
        return out

    @staticmethod
    def decode_outer(image: Image.Image, password_outer: str) -> bytes:
        working = LSBEngine._to_rgb_image(image)
        total_pix = working.width * working.height
        split_pix = total_pix // 2
        pix = list(working.getdata())
        enc = VaultEngine._read_zone(pix, 0, split_pix)
        try:
            return CryptoEngine.decrypt(enc, password_outer)
        except ValueError as exc:
            raise ValueError("Wrong password for outer vault") from exc

    @staticmethod
    def decode_inner(image: Image.Image, password_real: str) -> bytes:
        working = LSBEngine._to_rgb_image(image)
        total_pix = working.width * working.height
        split_pix = total_pix // 2
        pix = list(working.getdata())
        enc = VaultEngine._read_zone(pix, split_pix, total_pix)
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

    @staticmethod
    def _write_zone(pixels: list, start: int, end: int, payload: bytes):
        full = struct.pack(">I", len(payload)) + payload
        bits = [((b >> i) & 1) for b in full for i in range(7, -1, -1)]
        bp = 0
        for pi in range(start, end):
            if bp >= len(bits):
                break
            ch = list(pixels[pi])
            for c in range(3):
                if bp < len(bits):
                    ch[c] = (ch[c] & 0xFE) | bits[bp]
                    bp += 1
            pixels[pi] = tuple(ch)

    @staticmethod
    def _read_zone(pixels: list, start: int, end: int) -> bytes:
        bits = []
        for pi in range(start, end):
            for c in pixels[pi][:3]:
                bits.append(c & 1)
        length = 0
        for b in bits[:32]:
            length = (length << 1) | b
        needed = 32 + length * 8
        if needed > len(bits):
            raise ValueError("Zone too small for stored payload length")
        data = bytearray()
        for i in range(32, needed, 8):
            byte = 0
            for b in bits[i:i + 8]:
                byte = (byte << 1) | b
            data.append(byte)
        return bytes(data)
