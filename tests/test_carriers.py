import os
import struct
import tempfile
import wave
import pytest
from PIL import Image
from core.audio_engine import AudioEngine
from core.png_chunk_engine import PngChunkEngine


def _make_wav(path, n_samples=44100, value=1000):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(struct.pack("<" + "h" * n_samples, *([value] * n_samples)))


def _make_png(path, color=(123, 45, 67)):
    Image.new("RGB", (100, 100), color).save(path)


# ── Audio tests ──────────────────────────────────────────────────────────────

def test_audio_encode_decode(tmp_path):
    wav = str(tmp_path / "cover.wav")
    out = str(tmp_path / "stego.wav")
    _make_wav(wav)
    payload = b"audio hidden message"
    AudioEngine.encode(wav, payload, out)
    assert AudioEngine.decode(out) == payload


def test_audio_roundtrip_random_payload(tmp_path):
    wav = str(tmp_path / "cover.wav")
    out = str(tmp_path / "stego.wav")
    _make_wav(wav)
    payload = os.urandom(128)
    AudioEngine.encode(wav, payload, out)
    assert AudioEngine.decode(out) == payload


def test_audio_rejects_non_16bit(tmp_path):
    wav = str(tmp_path / "8bit.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(1)   # 8-bit
        w.setframerate(44100)
        w.writeframes(bytes(1000))
    with pytest.raises(ValueError, match="16-bit"):
        AudioEngine.encode(wav, b"x", str(tmp_path / "out.wav"))


def test_audio_capacity_error(tmp_path):
    wav = str(tmp_path / "tiny.wav")
    _make_wav(wav, n_samples=100)   # very short
    with pytest.raises(ValueError):
        AudioEngine.encode(wav, os.urandom(5000), str(tmp_path / "out.wav"))


def test_audio_capacity_bytes(tmp_path):
    wav = str(tmp_path / "cover.wav")
    _make_wav(wav)
    cap = AudioEngine.capacity_bytes(wav)
    assert cap > 0


# ── PNG chunk tests ───────────────────────────────────────────────────────────

def test_png_chunk_encode_decode(tmp_path):
    src = str(tmp_path / "cover.png")
    out = str(tmp_path / "stego.png")
    _make_png(src)
    payload = b"png chunk hidden message"
    PngChunkEngine.encode(src, payload, out)
    assert PngChunkEngine.decode(out) == payload


def test_png_chunk_has_payload(tmp_path):
    src = str(tmp_path / "cover.png")
    out = str(tmp_path / "stego.png")
    _make_png(src)
    assert not PngChunkEngine.has_payload(src)
    PngChunkEngine.encode(src, b"hello", out)
    assert PngChunkEngine.has_payload(out)


def test_png_chunk_visual_unchanged(tmp_path):
    src = str(tmp_path / "cover.png")
    out = str(tmp_path / "stego.png")
    color = (200, 100, 50)
    _make_png(src, color)
    PngChunkEngine.encode(src, b"invisible", out)
    original_px = list(Image.open(src).getdata())
    stego_px    = list(Image.open(out).getdata())
    assert original_px == stego_px


def test_png_chunk_no_payload_raises(tmp_path):
    src = str(tmp_path / "plain.png")
    _make_png(src)
    with pytest.raises(ValueError, match="[Nn]o.*[Ss]teg"):
        PngChunkEngine.decode(src)


def test_png_chunk_large_payload(tmp_path):
    src = str(tmp_path / "cover.png")
    out = str(tmp_path / "stego.png")
    _make_png(src)
    big = os.urandom(4096)
    PngChunkEngine.encode(src, big, out)
    assert PngChunkEngine.decode(out) == big


def test_png_chunk_rejects_non_png(tmp_path):
    bad = str(tmp_path / "notpng.txt")
    with open(bad, "wb") as f:
        f.write(b"this is not a png")
    with pytest.raises(ValueError):
        PngChunkEngine.decode(bad)
