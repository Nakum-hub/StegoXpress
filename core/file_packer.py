import os
import struct

from PIL import Image

from core.lsb_engine import LSBEngine


class FilePacker:
    TEXT_TYPE = 0x01
    FILE_TYPE = 0x02
    HEADER_OVERHEAD = 7

    @staticmethod
    def pack_text(message: str) -> bytes:
        data = message.encode("utf-8")
        return FilePacker._pack(FilePacker.TEXT_TYPE, b"", data)

    @staticmethod
    def pack_file(file_path: str) -> bytes:
        filename = os.path.basename(file_path).encode("utf-8")

        with open(file_path, "rb") as file:
            data = file.read()

        return FilePacker._pack(FilePacker.FILE_TYPE, filename, data)

    @staticmethod
    def unpack(payload: bytes) -> dict:
        if len(payload) < FilePacker.HEADER_OVERHEAD:
            raise ValueError("Malformed payload")

        payload_type = payload[0]
        filename_length = struct.unpack(">H", payload[1:3])[0]
        filename_start = 3
        filename_end = filename_start + filename_length
        data_length_start = filename_end
        data_length_end = data_length_start + 4

        if data_length_end > len(payload):
            raise ValueError("Malformed payload")

        filename_bytes = payload[filename_start:filename_end]
        data_length = struct.unpack(">I", payload[data_length_start:data_length_end])[0]
        data_start = data_length_end
        data_end = data_start + data_length

        if data_end != len(payload):
            raise ValueError("Malformed payload")

        data = payload[data_start:data_end]

        try:
            filename = filename_bytes.decode("utf-8") if filename_bytes else None
        except UnicodeDecodeError as exc:
            raise ValueError("Malformed payload") from exc

        if payload_type == FilePacker.TEXT_TYPE:
            if filename_length != 0:
                raise ValueError("Malformed payload")

            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("Malformed payload") from exc

            return {"type": "text", "filename": None, "data": data, "text": text}

        if payload_type == FilePacker.FILE_TYPE:
            return {"type": "file", "filename": filename, "data": data}

        raise ValueError("Malformed payload")

    @staticmethod
    def max_file_size_for_image(image: Image.Image) -> int:
        return LSBEngine.capacity_bytes(image) - FilePacker.HEADER_OVERHEAD

    @staticmethod
    def _pack(payload_type: int, filename: bytes, data: bytes) -> bytes:
        if len(filename) > 0xFFFF:
            raise ValueError("Filename too long")

        if len(data) > 0xFFFFFFFF:
            raise ValueError("Data too large")

        return (
            struct.pack(">B", payload_type)
            + struct.pack(">H", len(filename))
            + filename
            + struct.pack(">I", len(data))
            + data
        )
