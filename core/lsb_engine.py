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
    def _to_rgb_image(image: Image.Image) -> Image.Image:
        if "A" in image.getbands() or "transparency" in image.info:
            return image.convert("RGBA").convert("RGB")
        return image.convert("RGB")

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
