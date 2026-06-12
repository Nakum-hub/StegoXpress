import math
import os
import struct
from PIL import Image


class LSBEngine:
    # ──────────────────────────────────────────────
    # Standard encode / decode
    # ──────────────────────────────────────────────
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
        bit_iter = LSBEngine._make_bit_iter(full_data)
        out_pixels = []
        for pixel in list(working.getdata()):
            ch = list(pixel)
            for i in range(3):
                b = next(bit_iter, None)
                if b is None:
                    break
                ch[i] = (ch[i] & 0xFE) | b
            out_pixels.append(tuple(ch))
        out = Image.new("RGB", working.size)
        out.putdata(out_pixels)
        return out

    @staticmethod
    def decode(image: Image.Image) -> bytes:
        working = LSBEngine._to_rgb_image(image)
        bit_iter = LSBEngine._iter_lsb_bits(working)
        length = LSBEngine._bits_to_int(LSBEngine._read_bits(bit_iter, 32))
        return LSBEngine._bits_to_bytes(LSBEngine._read_bits(bit_iter, length * 8))

    @staticmethod
    def capacity_bytes(image: Image.Image) -> int:
        return (image.width * image.height * 3) // 8 - 4

    @staticmethod
    def bits_used_percent(image: Image.Image, payload_bytes: int) -> float:
        return ((payload_bytes + 4) * 8) / (image.width * image.height * 3) * 100

    # ──────────────────────────────────────────────
    # Erase (self-destruct support)
    # ──────────────────────────────────────────────
    @staticmethod
    def erase(image: Image.Image) -> Image.Image:
        """Zero out all LSBs — makes the image undecodable."""
        working = LSBEngine._to_rgb_image(image)
        erased = [(r & 0xFE, g & 0xFE, b & 0xFE) for r, g, b in list(working.getdata())]
        out = Image.new("RGB", working.size)
        out.putdata(erased)
        return out

    # ──────────────────────────────────────────────
    # Adaptive encode / decode (hides in high-entropy pixels)
    # ──────────────────────────────────────────────
    @staticmethod
    def adaptive_score(image: Image.Image) -> float:
        """Fraction of pixels with entropy > 0.4 — predicts adaptive mode benefit."""
        return LSBEngine._adaptive_score_threshold(image, 0.4)

    @staticmethod
    def encode_adaptive(image: Image.Image, payload: bytes) -> Image.Image:
        """
        Encode payload into pixels above an entropy threshold, in natural x,y order.
        HEADER: first 32 pixels (sequential LSB) hold [4B magic][4B payload_len][4B threshold_int].
        This gives a stable decode because both sides filter identically (natural order,
        stored threshold) and entropy values are stable to ±1-bit changes.
        """
        MAGIC = 0x41444150      # "ADAP"
        HEADER_PIX = 32         # 32 × 3 = 96 bits; need 96 bits for 12-byte header
        THRESHOLDS = [0.4, 0.3, 0.2, 0.1, 0.0]

        working = LSBEngine._to_rgb_image(image)
        w, h = working.size
        pixel_data = list(working.getdata())
        entropy_values = LSBEngine._compute_all_entropy(pixel_data, w, h)

        bits_needed = len(payload) * 8

        # Choose lowest threshold that gives enough pixels in natural order
        chosen_threshold = 0.0
        filtered = []
        for thr in THRESHOLDS:
            filtered = [i for i in range(HEADER_PIX, w * h) if entropy_values[i] >= thr]
            if len(filtered) * 3 >= bits_needed:
                chosen_threshold = thr
                break

        if len(filtered) * 3 < bits_needed:
            raise ValueError(
                f"Payload too large for adaptive mode: needs {bits_needed} bits, "
                f"have {len(filtered) * 3} bits available"
            )

        threshold_int = int(chosen_threshold * 100_000)
        out_pixels = list(pixel_data)

        # ── Write 12-byte header into first 32 pixels (sequential) ──
        header_data = struct.pack(">III", MAGIC, len(payload), threshold_int)
        hbits = list(LSBEngine._make_bit_iter(header_data))  # 96 bits
        bp = 0
        for pi in range(HEADER_PIX):
            ch = list(out_pixels[pi])
            for c in range(3):
                if bp < len(hbits):
                    ch[c] = (ch[c] & 0xFE) | hbits[bp]
                    bp += 1
            out_pixels[pi] = tuple(ch)

        # ── Write payload into filtered pixels (natural x,y order) ──
        pbits = list(LSBEngine._make_bit_iter(payload))
        bp = 0
        for pi in filtered:
            if bp >= len(pbits):
                break
            ch = list(out_pixels[pi])
            for c in range(3):
                if bp < len(pbits):
                    ch[c] = (ch[c] & 0xFE) | pbits[bp]
                    bp += 1
            out_pixels[pi] = tuple(ch)

        out = Image.new("RGB", working.size)
        out.putdata(out_pixels)
        return out

    @staticmethod
    def decode_adaptive(image: Image.Image) -> bytes:
        """
        Decode a payload written by encode_adaptive.
        Reads 12-byte header from first 32 pixels → magic, payload_length, threshold_int.
        Re-filters remaining pixels by threshold in natural order → reads payload bits.
        """
        MAGIC = 0x41444150
        HEADER_PIX = 32
        working = LSBEngine._to_rgb_image(image)
        w, h = working.size
        pixel_data = list(working.getdata())

        # Extract 96 header bits from first 32 pixels
        header_bits = []
        for pi in range(HEADER_PIX):
            for c in pixel_data[pi][:3]:
                header_bits.append(c & 1)

        magic         = LSBEngine._bits_to_int(header_bits[0:32])
        payload_length = LSBEngine._bits_to_int(header_bits[32:64])
        threshold_int  = LSBEngine._bits_to_int(header_bits[64:96])

        if magic != MAGIC:
            raise ValueError("Not an adaptive-encoded image (magic mismatch)")

        threshold = threshold_int / 100_000

        entropy_values = LSBEngine._compute_all_entropy(pixel_data, w, h)
        filtered = [i for i in range(HEADER_PIX, w * h) if entropy_values[i] >= threshold]

        raw_bits = []
        bits_needed = payload_length * 8
        for pi in filtered:
            if len(raw_bits) >= bits_needed:
                break
            for c in pixel_data[pi][:3]:
                if len(raw_bits) < bits_needed:
                    raw_bits.append(c & 1)

        if len(raw_bits) < bits_needed:
            raise ValueError("Not enough high-entropy pixels to decode payload")

        return LSBEngine._bits_to_bytes(raw_bits[:bits_needed])

    # ──────────────────────────────────────────────
    # Heatmap & steganalysis
    # ──────────────────────────────────────────────
    @staticmethod
    def generate_heatmap(image: Image.Image) -> Image.Image:
        working = image.convert("RGB")
        w, h = working.size
        pixels = working.load()
        heatmap = Image.new("RGB", (w, h))
        hp = heatmap.load()
        max_e = math.log2(75)
        for y in range(h):
            for x in range(w):
                vals = []
                for wy in range(max(0, y - 2), min(h, y + 3)):
                    for wx in range(max(0, x - 2), min(w, x + 3)):
                        vals.extend(pixels[wx, wy])
                total = len(vals)
                hist = {}
                for v in vals:
                    hist[v] = hist.get(v, 0) + 1
                ent = -sum((c / total) * math.log2(c / total) for c in hist.values() if c > 0)
                norm = min(ent / max_e, 1.0) if max_e else 0.0
                hp[x, y] = LSBEngine._entropy_color(norm)
        return heatmap

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

    # ──────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────
    @staticmethod
    def _to_rgb_image(image: Image.Image) -> Image.Image:
        if "A" in image.getbands() or "transparency" in image.info:
            return image.convert("RGBA").convert("RGB")
        return image.convert("RGB")

    @staticmethod
    def _make_bit_iter(data: bytes):
        for byte in data:
            for bit_index in range(7, -1, -1):
                yield (byte >> bit_index) & 1

    @staticmethod
    def _iter_lsb_bits(image: Image.Image):
        for pixel in list(image.getdata()):
            for channel in pixel[:3]:
                yield channel & 1

    @staticmethod
    def _read_bits(bit_iterator, bit_count: int) -> list:
        bits = []
        for _ in range(bit_count):
            try:
                bits.append(next(bit_iterator))
            except StopIteration as exc:
                raise ValueError("Image does not contain enough encoded data") from exc
        return bits

    @staticmethod
    def _bits_to_int(bits: list) -> int:
        v = 0
        for b in bits:
            v = (v << 1) | b
        return v

    @staticmethod
    def _bits_to_bytes(bits: list) -> bytes:
        out = bytearray()
        for i in range(0, len(bits), 8):
            byte = 0
            for b in bits[i:i + 8]:
                byte = (byte << 1) | b
            out.append(byte)
        return bytes(out)

    @staticmethod
    def _entropy_color(value: float) -> tuple:
        if value <= 0.5:
            r = 0.5
            r2 = value / 0.5
            return (0, round(255 * r2), round(255 * (1 - r2)))
        else:
            r2 = (value - 0.5) / 0.5
            return (round(255 * r2), round(255 * (1 - r2)), 0)

    @staticmethod
    def _pixel_intensity(pixel) -> int:
        return round((pixel[0] + pixel[1] + pixel[2]) / 3)

    @staticmethod
    def _smoothness(group: list) -> int:
        return sum(abs(group[i + 1] - group[i]) for i in range(len(group) - 1))

    @staticmethod
    def _compute_all_entropy(pixel_data: list, w: int, h: int) -> list:
        max_e = math.log2(75) if 75 > 1 else 1.0
        result = []
        for y in range(h):
            for x in range(w):
                vals = []
                for wy in range(max(0, y - 2), min(h, y + 3)):
                    for wx in range(max(0, x - 2), min(w, x + 3)):
                        vals.extend(pixel_data[wy * w + wx])
                total = len(vals)
                hist = {}
                for v in vals:
                    hist[v] = hist.get(v, 0) + 1
                ent = -sum((c / total) * math.log2(c / total) for c in hist.values() if c > 0)
                result.append(min(ent / max_e, 1.0) if max_e else 0.0)
        return result

    @staticmethod
    def _adaptive_score_threshold(image: Image.Image, threshold: float) -> float:
        working = LSBEngine._to_rgb_image(image)
        w, h = working.size
        pd = list(working.getdata())
        entropy_vals = LSBEngine._compute_all_entropy(pd, w, h)
        above = sum(1 for e in entropy_vals if e > threshold)
        return above / (w * h) if (w * h) > 0 else 0.0
