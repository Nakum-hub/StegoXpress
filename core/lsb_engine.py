import math
import struct
from PIL import Image


class LSBEngine:
    @staticmethod
    def encode(image: Image.Image, payload: bytes) -> Image.Image:
        working_image = LSBEngine._to_rgb_image(image)
        length_header = struct.pack(">I", len(payload))
        full_data = length_header + payload
        bits_needed = len(full_data) * 8
        capacity_bits = working_image.width * working_image.height * 3

        if bits_needed > capacity_bits:
            raise ValueError(
                f"Payload too large: needs {bits_needed} bits, image has {capacity_bits} bits"
            )

        bitstream = (
            (byte >> bit_index) & 1
            for byte in full_data
            for bit_index in range(7, -1, -1)
        )
        bit_iterator = iter(bitstream)
        encoded_pixels = []

        for pixel in working_image.getdata():
            channels = list(pixel)

            for channel_index in range(3):
                try:
                    bit = next(bit_iterator)
                except StopIteration:
                    break
                channels[channel_index] = (channels[channel_index] & 0xFE) | bit

            encoded_pixels.append(tuple(channels))

        encoded_image = Image.new("RGB", working_image.size)
        encoded_image.putdata(encoded_pixels)
        return encoded_image

    @staticmethod
    def decode(image: Image.Image) -> bytes:
        working_image = LSBEngine._to_rgb_image(image)
        bit_iterator = LSBEngine._iter_lsb_bits(working_image)

        header_bits = LSBEngine._read_bits(bit_iterator, 32)
        payload_length = LSBEngine._bits_to_int(header_bits)
        payload_bits = LSBEngine._read_bits(bit_iterator, payload_length * 8)
        return LSBEngine._bits_to_bytes(payload_bits)

    @staticmethod
    def capacity_bytes(image: Image.Image) -> int:
        return (image.width * image.height * 3) // 8 - 4

    @staticmethod
    def bits_used_percent(image: Image.Image, payload_bytes: int) -> float:
        return ((payload_bytes + 4) * 8) / (image.width * image.height * 3) * 100

    @staticmethod
    def generate_heatmap(image: Image.Image) -> Image.Image:
        working_image = image.convert("RGB")
        width, height = working_image.size
        pixels = working_image.load()
        heatmap = Image.new("RGB", working_image.size)
        heatmap_pixels = heatmap.load()
        max_entropy = math.log2(75)

        for y in range(height):
            for x in range(width):
                values = []

                for window_y in range(max(0, y - 2), min(height, y + 3)):
                    for window_x in range(max(0, x - 2), min(width, x + 3)):
                        values.extend(pixels[window_x, window_y])

                total = len(values)
                histogram = {}
                for value in values:
                    histogram[value] = histogram.get(value, 0) + 1

                entropy = 0.0
                for count in histogram.values():
                    probability = count / total
                    if probability > 0:
                        entropy -= probability * math.log2(probability)

                normalized = min(max(entropy / max_entropy, 0.0), 1.0)
                heatmap_pixels[x, y] = LSBEngine._entropy_color(normalized)

        return heatmap

    @staticmethod
    def steganalysis_score(original: Image.Image, stego: Image.Image) -> float:
        original_rgb = original.convert("RGB")
        stego_rgb = stego.convert("RGB")

        if original_rgb.size != stego_rgb.size:
            raise ValueError("Original and stego images must have the same size")

        width, height = stego_rgb.size
        if width < 8 or height == 0:
            return 0.0

        stego_pixels = stego_rgb.load()
        regular_count = 0
        singular_count = 0
        total_groups = 0
        flipping_mask = [0, 1, 0, 1, 0, 1, 0, 1]

        for y in range(height):
            for x in range(0, width - 7, 8):
                group = [
                    LSBEngine._pixel_intensity(stego_pixels[x + offset, y])
                    for offset in range(8)
                ]
                flipped = [
                    value ^ flipping_mask[index]
                    for index, value in enumerate(group)
                ]
                original_smoothness = LSBEngine._smoothness(group)
                flipped_smoothness = LSBEngine._smoothness(flipped)

                if flipped_smoothness > original_smoothness:
                    regular_count += 1
                elif flipped_smoothness < original_smoothness:
                    singular_count += 1

                total_groups += 1

        if total_groups == 0:
            return 0.0

        return min(abs(regular_count - singular_count) / total_groups, 1.0)

    @staticmethod
    def _to_rgb_image(image: Image.Image) -> Image.Image:
        if "A" in image.getbands() or "transparency" in image.info:
            return image.convert("RGBA").convert("RGB")
        return image.convert("RGB")

    @staticmethod
    def _entropy_color(value: float) -> tuple[int, int, int]:
        if value <= 0.5:
            ratio = value / 0.5
            red = 0
            green = round(255 * ratio)
            blue = round(255 * (1 - ratio))
        else:
            ratio = (value - 0.5) / 0.5
            red = round(255 * ratio)
            green = round(255 * (1 - ratio))
            blue = 0

        return red, green, blue

    @staticmethod
    def _pixel_intensity(pixel: tuple[int, int, int]) -> int:
        return round((pixel[0] + pixel[1] + pixel[2]) / 3)

    @staticmethod
    def _smoothness(group: list[int]) -> int:
        return sum(abs(group[index + 1] - group[index]) for index in range(7))

    @staticmethod
    def _iter_lsb_bits(image: Image.Image):
        for pixel in image.getdata():
            for channel in pixel[:3]:
                yield channel & 1

    @staticmethod
    def _read_bits(bit_iterator, bit_count: int) -> list[int]:
        bits = []

        for _ in range(bit_count):
            try:
                bits.append(next(bit_iterator))
            except StopIteration as exc:
                raise ValueError("Image does not contain enough encoded data") from exc

        return bits

    @staticmethod
    def _bits_to_int(bits: list[int]) -> int:
        value = 0

        for bit in bits:
            value = (value << 1) | bit

        return value

    @staticmethod
    def _bits_to_bytes(bits: list[int]) -> bytes:
        output = bytearray()

        for index in range(0, len(bits), 8):
            byte = 0
            for bit in bits[index : index + 8]:
                byte = (byte << 1) | bit
            output.append(byte)

        return bytes(output)
