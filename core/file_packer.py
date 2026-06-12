import hashlib
import hmac
import os
import struct

from PIL import Image

from core.lsb_engine import LSBEngine


class FilePacker:
    # ── Payload type bytes ──
    TEXT_TYPE          = 0x01
    FILE_TYPE          = 0x02
    VAULT_OUTER_TYPE   = 0x03   # decoy in dual-password vault
    VAULT_INNER_TYPE   = 0x04   # real   in dual-password vault
    SEALED_TYPE        = 0x05   # HMAC tamper-proof seal (text)
    SELF_DESTRUCT_TYPE = 0x06   # erase LSBs after first decode

    HEADER_OVERHEAD = 7     # type(1) + filename_len(2) + data_len(4)
    SEAL_SIZE       = 32    # HMAC-SHA256

    # ── Standard packing ──
    @staticmethod
    def pack_text(message: str) -> bytes:
        return FilePacker._pack(FilePacker.TEXT_TYPE, b"", message.encode("utf-8"))

    @staticmethod
    def pack_file(file_path: str) -> bytes:
        fname = os.path.basename(file_path).encode("utf-8")
        with open(file_path, "rb") as f:
            data = f.read()
        return FilePacker._pack(FilePacker.FILE_TYPE, fname, data)

    # ── Vault packing ──
    @staticmethod
    def pack_vault(decoy_message: str, real_message: str) -> tuple:
        """Returns (outer_payload_bytes, inner_payload_bytes)."""
        outer = FilePacker._pack(FilePacker.VAULT_OUTER_TYPE, b"", decoy_message.encode())
        inner = FilePacker._pack(FilePacker.VAULT_INNER_TYPE, b"", real_message.encode())
        return outer, inner

    @staticmethod
    def is_vault_outer(result: dict) -> bool:
        return result.get("type") == "vault_outer"

    @staticmethod
    def is_vault_inner(result: dict) -> bool:
        return result.get("type") == "vault_inner"

    # ── Sealed packing (HMAC tamper-proof) ──
    @staticmethod
    def pack_text_sealed(message: str, password: str) -> bytes:
        core = FilePacker._pack(FilePacker.SEALED_TYPE, b"", message.encode("utf-8"))
        mac = hmac.new(FilePacker.derive_seal_key(password), core, hashlib.sha256).digest()
        return core + mac

    @staticmethod
    def pack_file_sealed(file_path: str, password: str) -> bytes:
        fname = os.path.basename(file_path).encode("utf-8")
        with open(file_path, "rb") as f:
            data = f.read()
        core = FilePacker._pack(FilePacker.SEALED_TYPE, fname, data)
        mac = hmac.new(FilePacker.derive_seal_key(password), core, hashlib.sha256).digest()
        return core + mac

    @staticmethod
    def is_sealed(payload: bytes) -> bool:
        return len(payload) > 0 and payload[0] == FilePacker.SEALED_TYPE

    @staticmethod
    def verify_and_unpack_sealed(payload: bytes, password: str) -> dict:
        if len(payload) < FilePacker.HEADER_OVERHEAD + FilePacker.SEAL_SIZE + 1:
            raise ValueError("Sealed payload too short")
        core = payload[:-FilePacker.SEAL_SIZE]
        stored_mac = payload[-FilePacker.SEAL_SIZE:]
        key = FilePacker.derive_seal_key(password)
        expected_mac = hmac.new(key, core, hashlib.sha256).digest()
        if not hmac.compare_digest(stored_mac, expected_mac):
            raise ValueError("Seal broken — image was tampered with")
        return FilePacker.unpack(core)

    @staticmethod
    def derive_seal_key(password: str) -> bytes:
        return hashlib.sha256((password + ":stegoxpress-seal-v2").encode()).digest()

    # ── Self-destruct packing ──
    @staticmethod
    def pack_text_self_destruct(message: str) -> bytes:
        return FilePacker._pack(FilePacker.SELF_DESTRUCT_TYPE, b"", message.encode("utf-8"))

    @staticmethod
    def pack_file_self_destruct(file_path: str) -> bytes:
        fname = os.path.basename(file_path).encode("utf-8")
        with open(file_path, "rb") as f:
            data = f.read()
        return FilePacker._pack(FilePacker.SELF_DESTRUCT_TYPE, fname, data)

    @staticmethod
    def is_self_destruct(payload: bytes) -> bool:
        return len(payload) > 0 and payload[0] == FilePacker.SELF_DESTRUCT_TYPE

    # ── Unpack (all types) ──
    @staticmethod
    def unpack(payload: bytes) -> dict:
        if len(payload) < FilePacker.HEADER_OVERHEAD:
            raise ValueError("Malformed payload")

        ptype = payload[0]
        fname_len = struct.unpack(">H", payload[1:3])[0]
        fname_end = 3 + fname_len
        dlen_end  = fname_end + 4

        if dlen_end > len(payload):
            raise ValueError("Malformed payload")

        fname_bytes = payload[3:fname_end]
        data_len = struct.unpack(">I", payload[fname_end:dlen_end])[0]
        data_start = dlen_end
        data_end   = data_start + data_len

        # For sealed payloads the HMAC trailer may follow — allow it
        if data_end > len(payload):
            raise ValueError("Malformed payload")

        data = payload[data_start:data_end]
        try:
            fname = fname_bytes.decode("utf-8") if fname_bytes else None
        except UnicodeDecodeError as exc:
            raise ValueError("Malformed payload") from exc

        if ptype == FilePacker.TEXT_TYPE:
            return {"type": "text", "filename": None, "data": data, "text": data.decode("utf-8")}

        if ptype == FilePacker.FILE_TYPE:
            return {"type": "file", "filename": fname, "data": data}

        if ptype == FilePacker.VAULT_OUTER_TYPE:
            return {"type": "vault_outer", "filename": None, "data": data,
                    "text": data.decode("utf-8", errors="replace")}

        if ptype == FilePacker.VAULT_INNER_TYPE:
            return {"type": "vault_inner", "filename": None, "data": data,
                    "text": data.decode("utf-8", errors="replace")}

        if ptype == FilePacker.SEALED_TYPE:
            if not fname_bytes:  # text payload has empty filename
                return {"type": "sealed_text", "filename": None,
                        "data": data, "text": data.decode("utf-8", errors="replace")}
            return {"type": "sealed_file", "filename": fname, "data": data}

        if ptype == FilePacker.SELF_DESTRUCT_TYPE:
            if not fname_bytes:  # text payload has empty filename
                return {"type": "self_destruct_text", "filename": None,
                        "data": data, "text": data.decode("utf-8", errors="replace")}
            return {"type": "self_destruct_file", "filename": fname, "data": data}

        raise ValueError(f"Unknown payload type: {ptype:#04x}")

    # ── Capacity ──
    @staticmethod
    def max_file_size_for_image(image: Image.Image) -> int:
        return LSBEngine.capacity_bytes(image) - FilePacker.HEADER_OVERHEAD

    # ── Internal ──
    @staticmethod
    def _pack(ptype: int, fname: bytes, data: bytes) -> bytes:
        if len(fname) > 0xFFFF:
            raise ValueError("Filename too long")
        if len(data) > 0xFFFFFFFF:
            raise ValueError("Data too large")
        return (
            struct.pack(">B", ptype)
            + struct.pack(">H", len(fname))
            + fname
            + struct.pack(">I", len(data))
            + data
        )
