import math
import struct

import numpy as np
from PIL import Image

# Guard against decompression-bomb DoS on untrusted images (audit finding V6).
# Callers may raise this further; None disables the limit.
Image.MAX_IMAGE_PIXELS = 64_000_000  # ~64 megapixels


class LSBEngine:
    # ── Standard encode / decode ──
    @staticmethod
    def encode(image: Image.Image, payload: bytes) -> Image.Image:
        working = LSBEngine._to_rgb_image(image)
        full_data = struct.pack(">I", len(payload)) + payload
        bits_needed = len(full_data) * 8
        cap = working.width * working.height * 3
        if bits_needed > cap:
            raise ValueError(
                f"Payload too large: needs {bits_needed} bits, image has {cap} bits"
            )
        arr = np.asarray(working, dtype=np.uint8).reshape(-1).copy()
        bits = np.unpackbits(np.frombuffer(full_data, dtype=np.uint8))
        arr[:bits.size] = (arr[:bits.size] & 0xFE) | bits
        out = Image.new("RGB", working.size)
        out.putdata([tuple(p) for p in arr.reshape(-1, 3)])
        return out

    @staticmethod
    def decode(image: Image.Image) -> bytes:
        working = LSBEngine._to_rgb_image(image)
        flat = np.asarray(working, dtype=np.uint8).reshape(-1)
        lsb = flat & 1
        if lsb.size < 32:
            raise ValueError("Image does not contain enough encoded data")
        length = int(np.packbits(lsb[:32]).view(">u4")[0])
        need = 32 + length * 8
        if need > lsb.size:
            raise ValueError("Image does not contain enough encoded data")
        payload_bits = lsb[32:need]
        return np.packbits(payload_bits).tobytes()

    @staticmethod
    def capacity_bytes(image: Image.Image) -> int:
        return (image.width * image.height * 3) // 8 - 4

    @staticmethod
    def bits_used_percent(image: Image.Image, payload_bytes: int) -> float:
        return ((payload_bytes + 4) * 8) / (image.width * image.height * 3) * 100

    # ── Erase (self-destruct support) ──
    @staticmethod
    def erase(image: Image.Image) -> Image.Image:
        working = LSBEngine._to_rgb_image(image)
        arr = np.asarray(working, dtype=np.uint8) & 0xFE
        return Image.fromarray(arr, "RGB")

    # ── Adaptive encode / decode (hides in high-entropy pixels) ──
    # v2 (fixes audit finding V3): entropy is computed on LSB-masked pixel values
    # so the high-entropy pixel set is IDENTICAL before and after embedding. This
    # makes adaptive decode deterministic; previously decode could pick a
    # different pixel set and silently corrupt the payload. MAGIC bumped to ADA2.
    MAGIC_ADAPTIVE = 0x41444132  # "ADA2"
    HEADER_PIX = 32
    THRESHOLDS = [0.4, 0.3, 0.2, 0.1, 0.0]

    @staticmethod
    def adaptive_score(image: Image.Image) -> float:
        return LSBEngine._adaptive_score_threshold(image, 0.4)

    @staticmethod
    def encode_adaptive(image: Image.Image, payload: bytes) -> Image.Image:
        working = LSBEngine._to_rgb_image(image)
        w, h = working.size
        flat = np.asarray(working, dtype=np.uint8).reshape(-1, 3).copy()
        entropy_values = LSBEngine._compute_all_entropy_arr(flat, w, h)

        bits_needed = len(payload) * 8
        chosen_threshold = 0.0
        filtered = []
        for thr in LSBEngine.THRESHOLDS:
            filtered = [i for i in range(LSBEngine.HEADER_PIX, w * h)
                        if entropy_values[i] >= thr]
            if len(filtered) * 3 >= bits_needed:
                chosen_threshold = thr
                break
        if len(filtered) * 3 < bits_needed:
            raise ValueError(
                f"Payload too large for adaptive mode: needs {bits_needed} bits, "
                f"have {len(filtered) * 3} bits available"
            )

        threshold_int = int(chosen_threshold * 100_000)
        header = struct.pack(">III", LSBEngine.MAGIC_ADAPTIVE, len(payload), threshold_int)
        hbits = np.unpackbits(np.frombuffer(header, dtype=np.uint8))  # 96 bits

        # Write header into first 32 pixels (sequential, 3 bits/pixel)
        head = flat[:LSBEngine.HEADER_PIX].reshape(-1)
        head[:hbits.size] = (head[:hbits.size] & 0xFE) | hbits
        flat[:LSBEngine.HEADER_PIX] = head.reshape(-1, 3)

        # Write payload into filtered pixels (natural order)
        pbits = np.unpackbits(np.frombuffer(payload, dtype=np.uint8))
        bp = 0
        for pi in filtered:
            if bp >= pbits.size:
                break
            px = flat[pi]
            for c in range(3):
                if bp < pbits.size:
                    px[c] = (px[c] & 0xFE) | int(pbits[bp])
                    bp += 1
        out = Image.new("RGB", working.size)
        out.putdata([tuple(p) for p in flat])
        return out

    @staticmethod
    def decode_adaptive(image: Image.Image) -> bytes:
        working = LSBEngine._to_rgb_image(image)
        w, h = working.size
        flat = np.asarray(working, dtype=np.uint8).reshape(-1, 3)

        head_bits = (flat[:LSBEngine.HEADER_PIX].reshape(-1) & 1).astype(np.uint8)
        magic = int(np.packbits(head_bits[0:32]).view(">u4")[0])
        payload_length = int(np.packbits(head_bits[32:64]).view(">u4")[0])
        threshold_int = int(np.packbits(head_bits[64:96]).view(">u4")[0])
        if magic != LSBEngine.MAGIC_ADAPTIVE:
            raise ValueError("Not an adaptive-encoded image (magic mismatch)")
        threshold = threshold_int / 100_000

        entropy_values = LSBEngine._compute_all_entropy_arr(flat, w, h)
        filtered = [i for i in range(LSBEngine.HEADER_PIX, w * h)
                    if entropy_values[i] >= threshold]

        bits_needed = payload_length * 8
        raw_bits = []
        for pi in filtered:
            if len(raw_bits) >= bits_needed:
                break
            for c in flat[pi][:3]:
                if len(raw_bits) < bits_needed:
                    raw_bits.append(int(c) & 1)
        if len(raw_bits) < bits_needed:
            raise ValueError("Not enough high-entropy pixels to decode payload")
        return np.packbits(np.array(raw_bits[:bits_needed], dtype=np.uint8)).tobytes()

    # ── Heatmap & steganalysis ──
    @staticmethod
    def generate_heatmap(image: Image.Image) -> Image.Image:
        working = image.convert("RGB")
        w, h = working.size
        flat = np.asarray(working, dtype=np.uint8).reshape(-1, 3)
        norm = LSBEngine._entropy_norm_map(flat, w, h, mask_lsb=False).reshape(h, w)
        low = norm <= 0.5
        r2_low = norm / 0.5
        r2_high = (norm - 0.5) / 0.5
        R = np.where(low, 0, np.round(255 * r2_high))
        G = np.where(low, np.round(255 * r2_low), np.round(255 * (1 - r2_high)))
        B = np.where(low, np.round(255 * (1 - r2_low)), 0)
        rgb = np.clip(np.stack([R, G, B], axis=-1), 0, 255).astype(np.uint8)
        return Image.fromarray(rgb, "RGB")

    @staticmethod
    def steganalysis_score(original: Image.Image, stego: Image.Image) -> float:
        orig = original.convert("RGB")
        st = stego.convert("RGB")
        if orig.size != st.size:
            raise ValueError("Images must be the same size")
        w, h = st.size
        if w < 8:
            return 0.0
        sp = st.load()
        reg = sing = total = 0
        mask = [0, 1, 0, 1, 0, 1, 0, 1]
        for y in range(h):
            for x in range(0, w - 7, 8):
                grp = [LSBEngine._pixel_intensity(sp[x + k, y]) for k in range(8)]
                flp = [v ^ mask[i] for i, v in enumerate(grp)]
                os_ = LSBEngine._smoothness(grp)
                fs = LSBEngine._smoothness(flp)
                if fs > os_:
                    reg += 1
                elif fs < os_:
                    sing += 1
                total += 1
        return min(abs(reg - sing) / total, 1.0) if total else 0.0

    # ── Private helpers ──
    @staticmethod
    def _to_rgb_image(image: Image.Image) -> Image.Image:
        if "A" in image.getbands() or "transparency" in image.info:
            return image.convert("RGBA").convert("RGB")
        return image.convert("RGB")

    @staticmethod
    def _pixel_intensity(pixel) -> int:
        return round((pixel[0] + pixel[1] + pixel[2]) / 3)

    @staticmethod
    def _smoothness(group: list) -> int:
        return sum(abs(group[i + 1] - group[i]) for i in range(len(group) - 1))

    @staticmethod
    def _compute_all_entropy_arr(flat_rgb: np.ndarray, w: int, h: int) -> np.ndarray:
        """Return a flat (w*h,) array of normalized window entropy, LSB-masked."""
        return LSBEngine._entropy_norm_map(flat_rgb, w, h, mask_lsb=True).reshape(-1)

    @staticmethod
    def _entropy_norm_map(flat_rgb: np.ndarray, w: int, h: int,
                          mask_lsb: bool) -> np.ndarray:
        arr = flat_rgb.reshape(h, w, 3)
        if mask_lsb:
            m = ((arr & 0xFE) >> 1).astype(np.intp)  # 0..127
            nbins = 128
        else:
            m = arr.astype(np.intp)                  # 0..255
            nbins = 256
        pad = np.pad(m, ((2, 2), (2, 2), (0, 0)), mode="edge")
        counts = np.zeros((h, w, nbins), dtype=np.uint16)
        ii, jj = np.indices((h, w))
        for dy in range(5):
            for dx in range(5):
                block = pad[dy:dy + h, dx:dx + w, :]
                for c in range(3):
                    np.add.at(counts, (ii, jj, block[:, :, c]), 1)
        total = 75.0
        p = counts.astype(np.float32) / total
        logp = np.zeros_like(p)
        nz = p > 0
        logp[nz] = np.log2(p[nz])
        ent = -(p * logp).sum(axis=2)
        max_e = math.log2(75)
        return np.minimum(ent / max_e, 1.0).astype(np.float32)

    @staticmethod
    def _adaptive_score_threshold(image: Image.Image, threshold: float) -> float:
        working = LSBEngine._to_rgb_image(image)
        w, h = working.size
        flat = np.asarray(working, dtype=np.uint8).reshape(-1, 3)
        entropy_vals = LSBEngine._compute_all_entropy_arr(flat, w, h)
        above = int(np.count_nonzero(entropy_vals > threshold))
        return above / (w * h) if (w * h) > 0 else 0.0
