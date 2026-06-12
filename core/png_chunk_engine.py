"""
PngChunkEngine — hide data in a private PNG ancillary chunk ("stXp").
The image renders identically in all viewers — the chunk is ignored by
all standard PNG decoders. No pixel values are modified.
"""
import struct
import zlib

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
CHUNK_TYPE    = b"stXp"       # private = lowercase first letter (ancillary)
IEND_CHUNK    = b"\x00\x00\x00\x00IEND\xaeB`\x82"


class PngChunkEngine:

    @staticmethod
    def encode(png_path: str, payload: bytes, output_path: str) -> None:
        with open(png_path, "rb") as f:
            raw = f.read()

        PngChunkEngine._verify_png(raw)

        # Find IEND position
        iend_pos = raw.rfind(IEND_CHUNK)
        if iend_pos == -1:
            raise ValueError("Malformed PNG: IEND chunk not found")

        # Build custom chunk: length(4) + type(4) + data + crc(4)
        crc_val = zlib.crc32(CHUNK_TYPE + payload) & 0xFFFFFFFF
        custom_chunk = (
            struct.pack(">I", len(payload))
            + CHUNK_TYPE
            + payload
            + struct.pack(">I", crc_val)
        )

        # Insert before IEND
        new_raw = raw[:iend_pos] + custom_chunk + raw[iend_pos:]

        with open(output_path, "wb") as f:
            f.write(new_raw)

    @staticmethod
    def decode(png_path: str) -> bytes:
        with open(png_path, "rb") as f:
            raw = f.read()

        PngChunkEngine._verify_png(raw)

        # Walk chunks to find stXp
        pos = len(PNG_SIGNATURE)
        while pos < len(raw):
            if pos + 8 > len(raw):
                break
            chunk_len = struct.unpack(">I", raw[pos:pos + 4])[0]
            chunk_type = raw[pos + 4:pos + 8]
            chunk_data = raw[pos + 8:pos + 8 + chunk_len]
            chunk_crc  = struct.unpack(">I", raw[pos + 8 + chunk_len:pos + 12 + chunk_len])[0]

            if chunk_type == CHUNK_TYPE:
                expected_crc = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
                if chunk_crc != expected_crc:
                    raise ValueError("stXp chunk CRC mismatch — data may be corrupted")
                return chunk_data

            pos += 12 + chunk_len

        raise ValueError("No StegoXpress chunk (stXp) found in this PNG")

    @staticmethod
    def has_payload(png_path: str) -> bool:
        try:
            PngChunkEngine.decode(png_path)
            return True
        except ValueError:
            return False

    @staticmethod
    def capacity_bytes() -> int:
        # PNG spec allows chunks up to 2^31 - 1 bytes; practical limit is file size
        return 2 * 1024 * 1024 * 1024

    @staticmethod
    def _verify_png(raw: bytes) -> None:
        if not raw.startswith(PNG_SIGNATURE):
            raise ValueError("File is not a valid PNG")
