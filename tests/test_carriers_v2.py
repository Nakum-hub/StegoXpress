"""
Carrier + robustness tests for StegoXpress v2.

Covers:
  1. Audio (WAV) carrier roundtrip
  2. PNG metadata chunk carrier roundtrip
  3. Fuzzing: random bytes into FilePacker.unpack must raise ValueError, never crash
  4. Fuzzing: random bytes into CryptoEngine.decrypt must raise ValueError
  5. CLI module imports cleanly

Run:  python3 tests/test_carriers_v2.py
"""
import os
import struct
import sys
import tempfile
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.audio_engine import AudioEngine
from core.crypto_engine import CryptoEngine
from core.file_packer import FilePacker
from core.png_chunk_engine import PngChunkEngine

from PIL import Image

PASSED = 0
FAILED = 0


def check(name, fn):
    global PASSED, FAILED
    try:
        fn()
        PASSED += 1
        print(f"  PASS  {name}")
    except Exception as exc:
        FAILED += 1
        print(f"  FAIL  {name}: {exc!r}")


def make_wav(path, seconds=2, rate=8000):
    """Create a small 16-bit PCM mono WAV with deterministic pseudo-audio."""
    nframes = seconds * rate
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = b"".join(
            struct.pack("<h", (i * 37 % 32767) - 16384) for i in range(nframes)
        )
        w.writeframes(frames)


def test_audio_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "cover.wav")
        out = os.path.join(d, "stego.wav")
        make_wav(src)
        secret = b"audio carrier secret \x00\xff payload" * 10
        AudioEngine.encode(src, secret, out)
        recovered = AudioEngine.decode(out)
        assert recovered == secret, "audio roundtrip mismatch"


def test_audio_capacity_enforced():
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "tiny.wav")
        out = os.path.join(d, "stego.wav")
        make_wav(src, seconds=1, rate=800)  # tiny capacity
        too_big = os.urandom(64_000)
        try:
            AudioEngine.encode(src, too_big, out)
            raise AssertionError("expected ValueError for oversized payload")
        except ValueError:
            pass


def test_png_chunk_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "cover.png")
        out = os.path.join(d, "stego.png")
        Image.new("RGB", (64, 64), (10, 20, 30)).save(src, "PNG")
        secret = os.urandom(4096)
        PngChunkEngine.encode(src, secret, out)
        recovered = PngChunkEngine.decode(out)
        assert recovered == secret, "png chunk roundtrip mismatch"
        # Pixels must be untouched
        with Image.open(out) as img:
            assert img.getpixel((0, 0)) == (10, 20, 30), "pixels modified"


def test_png_chunk_missing():
    with tempfile.TemporaryDirectory() as d:
        plain = os.path.join(d, "plain.png")
        Image.new("RGB", (8, 8)).save(plain, "PNG")
        try:
            PngChunkEngine.decode(plain)
            raise AssertionError("expected ValueError for image without chunk")
        except ValueError:
            pass


def test_fuzz_unpack_never_crashes():
    """Random garbage into FilePacker.unpack must raise ValueError, never
    IndexError/struct.error/KeyError or hang."""
    import random
    rng = random.Random(1337)
    for i in range(300):
        size = rng.randint(0, 512)
        blob = os.urandom(size)
        try:
            FilePacker.unpack(blob)
        except ValueError:
            continue  # the only acceptable failure mode
        except Exception as exc:
            raise AssertionError(
                f"iteration {i}: unpack raised {type(exc).__name__} instead of ValueError"
            )
        # If unpack accepted random bytes, type byte must at least be valid —
        # extremely unlikely but not an error in itself for crafted sizes.


def test_fuzz_decrypt_never_crashes():
    for i in range(100):
        blob = os.urandom(64 + (i % 64))
        try:
            CryptoEngine.decrypt(blob, "any-password")
            raise AssertionError(f"iteration {i}: decrypt accepted random bytes")
        except ValueError:
            continue
        except Exception as exc:
            raise AssertionError(
                f"iteration {i}: decrypt raised {type(exc).__name__} instead of ValueError"
            )


def test_sealed_text_tamper_detection():
    pw = "correct horse battery staple"
    packed = FilePacker.pack_text_sealed("top secret", pw)
    result = FilePacker.verify_and_unpack_sealed(packed, pw)
    assert result["text"] == "top secret"
    # Flip a byte in the core payload — seal must reject it
    tampered = bytearray(packed)
    tampered[5] ^= 0xFF
    try:
        FilePacker.verify_and_unpack_sealed(bytes(tampered), pw)
        raise AssertionError("tampered seal was accepted")
    except ValueError:
        pass


def test_cli_imports():
    import importlib
    mod = importlib.import_module("main")
    assert hasattr(mod, "main"), "main.py must expose main()"


if __name__ == "__main__":
    print("StegoXpress v2 — carrier & robustness tests")
    check("audio WAV roundtrip", test_audio_roundtrip)
    check("audio capacity enforced", test_audio_capacity_enforced)
    check("PNG chunk roundtrip (pixels untouched)", test_png_chunk_roundtrip)
    check("PNG chunk missing -> ValueError", test_png_chunk_missing)
    check("fuzz: unpack never crashes", test_fuzz_unpack_never_crashes)
    check("fuzz: decrypt never crashes", test_fuzz_decrypt_never_crashes)
    check("sealed text tamper detection", test_sealed_text_tamper_detection)
    check("CLI module imports", test_cli_imports)
    print(f"\n{PASSED} passed, {FAILED} failed")
    sys.exit(1 if FAILED else 0)
