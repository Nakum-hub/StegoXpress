import os
import pytest
from PIL import Image
from core.file_packer import FilePacker
from core.lsb_engine import LSBEngine


# ── Sealed payload ───────────────────────────────────────────────────────────

def test_seal_roundtrip_text():
    packed = FilePacker.pack_text_sealed("sealed message", "mypassword")
    assert FilePacker.is_sealed(packed)
    result = FilePacker.verify_and_unpack_sealed(packed, "mypassword")
    assert result["text"] == "sealed message"


def test_seal_roundtrip_file(tmp_path):
    f = tmp_path / "doc.txt"
    f.write_bytes(b"file content here")
    packed = FilePacker.pack_file_sealed(str(f), "filepass")
    assert FilePacker.is_sealed(packed)
    result = FilePacker.verify_and_unpack_sealed(packed, "filepass")
    assert result["data"] == b"file content here"


def test_seal_tamper_detected():
    packed = FilePacker.pack_text_sealed("sealed", "pass")
    tampered = bytearray(packed)
    tampered[10] ^= 0xFF
    with pytest.raises(ValueError, match="[Tt]amper"):
        FilePacker.verify_and_unpack_sealed(bytes(tampered), "pass")


def test_seal_wrong_password_rejected():
    packed = FilePacker.pack_text_sealed("sealed", "correctpass")
    with pytest.raises(ValueError):
        FilePacker.verify_and_unpack_sealed(packed, "wrongpass")


def test_seal_type_byte():
    packed = FilePacker.pack_text_sealed("x", "p")
    assert packed[0] == FilePacker.SEALED_TYPE


def test_seal_derive_key_deterministic():
    k1 = FilePacker.derive_seal_key("mypass")
    k2 = FilePacker.derive_seal_key("mypass")
    assert k1 == k2 and len(k1) == 32


def test_seal_different_passwords_different_keys():
    assert FilePacker.derive_seal_key("aaa") != FilePacker.derive_seal_key("bbb")


# ── Self-destruct payload ─────────────────────────────────────────────────────

def test_self_destruct_pack_unpack_text():
    packed = FilePacker.pack_text_self_destruct("destruct me")
    assert FilePacker.is_self_destruct(packed)
    result = FilePacker.unpack(packed)
    assert result["type"] == "self_destruct_text"
    assert result["text"] == "destruct me"


def test_self_destruct_pack_unpack_file(tmp_path):
    f = tmp_path / "secret.bin"
    f.write_bytes(bytes(range(50)))
    packed = FilePacker.pack_file_self_destruct(str(f))
    assert FilePacker.is_self_destruct(packed)
    result = FilePacker.unpack(packed)
    assert result["type"] == "self_destruct_file"
    assert result["data"] == bytes(range(50))


def test_self_destruct_type_byte():
    packed = FilePacker.pack_text_self_destruct("x")
    assert packed[0] == FilePacker.SELF_DESTRUCT_TYPE


# ── LSBEngine.erase ───────────────────────────────────────────────────────────

def test_erase_clears_lsb_layer():
    img = Image.new("RGB", (100, 100), "white")
    stego = LSBEngine.encode(img, b"erase me please")
    erased = LSBEngine.erase(stego)
    # All LSBs must be zero
    for pixel in list(erased.getdata()):
        for ch in pixel:
            assert (ch & 1) == 0, f"LSB not cleared: {ch}"


def test_erase_makes_decode_return_zero_length():
    img = Image.new("RGB", (100, 100), "white")
    stego = LSBEngine.encode(img, b"will be erased")
    erased = LSBEngine.erase(stego)
    # Length header is now all zeros → decode returns empty bytes
    result = LSBEngine.decode(erased)
    assert result == b""


def test_erase_preserves_image_size():
    img = Image.new("RGB", (200, 150), (100, 150, 200))
    stego = LSBEngine.encode(img, b"x" * 100)
    erased = LSBEngine.erase(stego)
    assert erased.size == img.size
    assert erased.mode == "RGB"


# ── Adaptive encode/decode ────────────────────────────────────────────────────

def test_adaptive_roundtrip_random_image():
    import random
    random.seed(99)
    pixels = [tuple(random.randint(0, 255) for _ in range(3)) for _ in range(200 * 200)]
    img = Image.new("RGB", (200, 200))
    img.putdata(pixels)
    payload = b"adaptive encode decode test"
    stego = LSBEngine.encode_adaptive(img, payload)
    assert LSBEngine.decode_adaptive(stego) == payload


def test_adaptive_roundtrip_varied_message():
    import random
    random.seed(7)
    pixels = [tuple(random.randint(0, 255) for _ in range(3)) for _ in range(200 * 200)]
    img = Image.new("RGB", (200, 200))
    img.putdata(pixels)
    msg = b"Unicode test: \xe2\x9c\x93 done"
    stego = LSBEngine.encode_adaptive(img, msg)
    assert LSBEngine.decode_adaptive(stego) == msg


def test_adaptive_score_range():
    img = Image.new("RGB", (30, 30), "white")
    score = LSBEngine.adaptive_score(img)
    assert 0.0 <= score <= 1.0


def test_adaptive_wrong_magic_raises():
    img = Image.new("RGB", (100, 100), "white")
    # Standard-encoded image has no ADAP magic
    stego = LSBEngine.encode(img, b"standard encoded")
    with pytest.raises(ValueError, match="[Mm]agic"):
        LSBEngine.decode_adaptive(stego)
