from io import BytesIO
import os

import pytest
from PIL import Image

from core.crypto_engine import CryptoEngine
from core.file_packer import FilePacker
from core.lsb_engine import LSBEngine


def test_short_message():
    payload = b"Hello, World!"
    image = Image.new("RGB", (100, 100), "white")

    encoded = LSBEngine.encode(image, payload)
    decoded = LSBEngine.decode(encoded)

    assert decoded == payload


def test_long_message():
    payload = os.urandom(1000)
    image = Image.new("RGB", (200, 200), "white")

    encoded = LSBEngine.encode(image, payload)
    decoded = LSBEngine.decode(encoded)

    assert decoded == payload


def test_capacity_error():
    payload = os.urandom(100 * 1024)
    image = Image.new("RGB", (10, 10), "white")

    with pytest.raises(ValueError):
        LSBEngine.encode(image, payload)


def test_crypto_roundtrip():
    plaintext = "secret message".encode()
    encrypted = CryptoEngine.encrypt(plaintext, "mypassword")
    decrypted = CryptoEngine.decrypt(encrypted, "mypassword")

    assert decrypted == plaintext


def test_wrong_password():
    encrypted = CryptoEngine.encrypt(b"secret message", "mypassword")

    with pytest.raises(ValueError):
        CryptoEngine.decrypt(encrypted, "wrongpassword")


def test_full_pipeline():
    original_text = "StegoXpress full pipeline"
    password = "correct horse battery staple"
    image = Image.new("RGB", (150, 150), "white")

    encrypted = CryptoEngine.encrypt(original_text.encode("utf-8"), password)
    encoded_image = LSBEngine.encode(image, encrypted)
    decoded_encrypted = LSBEngine.decode(encoded_image)
    decrypted = CryptoEngine.decrypt(decoded_encrypted, password)

    assert decrypted.decode("utf-8") == original_text


def test_rgba_image():
    payload = b"rgba payload"
    image = Image.new("RGBA", (100, 100), (255, 255, 255, 128))

    encoded = LSBEngine.encode(image, payload)
    decoded = LSBEngine.decode(encoded)

    assert encoded.mode == "RGB"
    assert decoded == payload


def test_jpg_converted(tmp_path):
    payload = b"jpeg converted payload"
    jpeg_buffer = BytesIO()
    original = Image.new("RGB", (100, 100), "white")
    original.save(jpeg_buffer, format="JPEG")
    jpeg_buffer.seek(0)

    jpeg_image = Image.open(jpeg_buffer)
    encoded = LSBEngine.encode(jpeg_image, payload)
    output_path = tmp_path / "encoded.png"
    encoded.save(output_path, format="PNG")

    decoded = LSBEngine.decode(Image.open(output_path))

    assert decoded == payload


def test_pack_text():
    packed = FilePacker.pack_text("Hello")
    unpacked = FilePacker.unpack(packed)

    assert unpacked["type"] == "text"
    assert unpacked["text"] == "Hello"


def test_pack_file(tmp_path):
    file_path = tmp_path / "hidden.png"
    Image.new("RGB", (10, 10), "white").save(file_path, format="PNG")
    original_bytes = file_path.read_bytes()

    packed = FilePacker.pack_file(str(file_path))
    unpacked = FilePacker.unpack(packed)

    assert unpacked["type"] == "file"
    assert unpacked["filename"] == "hidden.png"
    assert unpacked["data"] == original_bytes


def test_file_hidden_in_image(tmp_path):
    file_path = tmp_path / "sample.pdf"
    original_bytes = b"%PDF-1.4\n" + bytes(range(91))
    file_path.write_bytes(original_bytes)
    password = "file-password"
    image = Image.new("RGB", (500, 500), "white")

    packed = FilePacker.pack_file(str(file_path))
    encrypted = CryptoEngine.encrypt(packed, password)
    encoded = LSBEngine.encode(image, encrypted)
    decoded_encrypted = LSBEngine.decode(encoded)
    decrypted = CryptoEngine.decrypt(decoded_encrypted, password)
    unpacked = FilePacker.unpack(decrypted)

    assert unpacked["type"] == "file"
    assert unpacked["filename"] == "sample.pdf"
    assert unpacked["data"] == original_bytes


def test_type_detection(tmp_path):
    text_payload = FilePacker.unpack(FilePacker.pack_text("Hello"))
    file_path = tmp_path / "data.bin"
    file_path.write_bytes(b"binary-data")
    file_payload = FilePacker.unpack(FilePacker.pack_file(str(file_path)))

    assert text_payload["type"] == "text"
    assert file_payload["type"] == "file"


# ── New tests added by upgrade ────────────────────────────────────────────────

def test_unicode_text_roundtrip():
    message = "ಕನ್ನಡ \U0001f512 \u0645\u0631\u062d\u0628\u0627 \u2014 secure"
    password = "unicode-test-pw"
    image = Image.new("RGB", (200, 200), "white")
    packed = FilePacker.pack_text(message)
    encrypted = CryptoEngine.encrypt(packed, password)
    encoded = LSBEngine.encode(image, encrypted)
    decrypted = CryptoEngine.decrypt(LSBEngine.decode(encoded), password)
    assert FilePacker.unpack(decrypted)["text"] == message


def test_capacity_bytes_helper():
    image = Image.new("RGB", (100, 100), "white")
    assert LSBEngine.capacity_bytes(image) == (100 * 100 * 3) // 8 - 4


def test_bits_used_percent_helper():
    image = Image.new("RGB", (100, 100), "white")
    pct = LSBEngine.bits_used_percent(image, 100)
    assert 0 < pct < 100
    full_pct = LSBEngine.bits_used_percent(image, LSBEngine.capacity_bytes(image))
    assert full_pct <= 100.1


def test_heatmap_returns_rgb_same_size():
    image = Image.new("RGB", (30, 30), (128, 64, 32))
    heatmap = LSBEngine.generate_heatmap(image)
    assert heatmap.mode == "RGB"
    assert heatmap.size == image.size


def test_steganalysis_score_bounds():
    image = Image.new("RGB", (100, 100), "white")
    score = LSBEngine.steganalysis_score(image, image)
    assert 0.0 <= score <= 1.0


def test_steganalysis_score_encoded_image():
    image = Image.new("RGB", (100, 100), "white")
    stego = LSBEngine.encode(image, os.urandom(200))
    score = LSBEngine.steganalysis_score(image, stego)
    assert 0.0 <= score <= 1.0


def test_empty_message_roundtrip():
    image = Image.new("RGB", (50, 50), "white")
    packed = FilePacker.pack_text("")
    encrypted = CryptoEngine.encrypt(packed, "emptypass")
    stego = LSBEngine.encode(image, encrypted)
    decrypted = CryptoEngine.decrypt(LSBEngine.decode(stego), "emptypass")
    assert FilePacker.unpack(decrypted)["text"] == ""
