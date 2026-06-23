"""
Production-readiness tests for StegoXpress v2.1.

Covers everything not already in test_upgrade.py / test_carriers_v2.py:
  - CLI: env-var password, --seal, --adaptive, --carrier flags, --json output,
         wrong-password exit code, png-chunk and audio via CLI
  - PersistentHistory: add / clear / persistence roundtrip
  - VaultEngine: NumPy rewrite still passes roundtrip (no deprecated-API warnings)
  - EmailSender: subject defaulting, custom subject, body hint
  - CryptoEngine: version flag in output
"""
import json
import os
import struct
import sys
import tempfile
import wave
import warnings

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.crypto_engine import CryptoEngine
from core.file_packer import FilePacker
from core.lsb_engine import LSBEngine
from core.vault_engine import VaultEngine
from transport.email_sender import EmailSender
from utils.history import PersistentHistory


# ── Helpers ──────────────────────────────────────────────────────────────────

def _rand_image(w=128, h=128, seed=99):
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)
    return Image.fromarray(arr, "RGB")


def _make_wav(path, seconds=2, rate=8000):
    nframes = seconds * rate
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = b"".join(
            struct.pack("<h", (i * 37 % 32767) - 16384) for i in range(nframes)
        )
        w.writeframes(frames)


def _run_cli(*args):
    """Run main.run_cli and return exit code."""
    import main as m
    return m.run_cli(list(args))


# ── CLI: env-var password ────────────────────────────────────────────────────

def test_cli_env_var_password(tmp_path):
    """STEGO_PASSWORD env var replaces --password flag."""
    img = _rand_image()
    cover = str(tmp_path / "cover.png")
    out = str(tmp_path / "stego.png")
    img.save(cover)

    os.environ["STEGO_PASSWORD"] = "env-var-test-pass!"
    try:
        rc = _run_cli("encode", "--image", cover, "--text", "hello env", "--output", out)
        assert rc == 0, "encode with env-var password failed"
        rc = _run_cli("decode", "--image", out)
        assert rc == 0, "decode with env-var password failed"
    finally:
        del os.environ["STEGO_PASSWORD"]


def test_cli_no_password_returns_error(tmp_path):
    """Missing password (no flag, no env var) must exit non-zero."""
    img = _rand_image()
    cover = str(tmp_path / "cover.png")
    img.save(cover)
    os.environ.pop("STEGO_PASSWORD", None)
    rc = _run_cli("encode", "--image", cover, "--text", "x", "--output", str(tmp_path / "out.png"))
    assert rc != 0


# ── CLI: --seal ───────────────────────────────────────────────────────────────

def test_cli_seal_roundtrip(tmp_path):
    img = _rand_image()
    cover = str(tmp_path / "cover.png")
    out = str(tmp_path / "sealed.png")
    img.save(cover)
    pw = "seal-test-pw-2026!"

    rc = _run_cli("encode", "--image", cover, "--text", "sealed secret",
                  "--password", pw, "--seal", "--output", out)
    assert rc == 0

    rc = _run_cli("decode", "--image", out, "--password", pw, "--verify-seal")
    assert rc == 0


def test_cli_seal_verify_detects_tamper(tmp_path):
    """verify-seal must return non-zero exit when payload is tampered."""
    img = _rand_image()
    cover = str(tmp_path / "cover.png")
    out = str(tmp_path / "sealed.png")
    img.save(cover)
    pw = "seal-tamper-test!"

    _run_cli("encode", "--image", cover, "--text", "will be tampered",
             "--password", pw, "--seal", "--output", out)

    # Flip a bit WITHIN the payload area (payload ≈ 75 bytes = 600 bits ≈ first 200 pixels).
    # Pixel (0, 50) = flat index 50, bit position 150 — well inside the encrypted payload.
    with Image.open(out) as im:
        arr = np.asarray(im.convert("RGB"), dtype=np.uint8).copy()
    arr[0, 50, 1] ^= 0x01  # flip channel G of pixel (row=0, col=50)
    Image.fromarray(arr, "RGB").save(out, "PNG")

    rc = _run_cli("decode", "--image", out, "--password", pw, "--verify-seal")
    assert rc != 0, "tampered seal should have caused a non-zero exit"


# ── CLI: --carrier image-adaptive ────────────────────────────────────────────

def test_cli_adaptive_roundtrip(tmp_path):
    img = _rand_image(256, 256, seed=42)
    cover = str(tmp_path / "cover.png")
    out = str(tmp_path / "adaptive.png")
    img.save(cover)
    pw = "adaptive-test-pw!"

    rc = _run_cli("encode", "--image", cover, "--text", "adaptive payload",
                  "--password", pw, "--carrier", "image-adaptive", "--output", out)
    assert rc == 0

    rc = _run_cli("decode", "--image", out, "--password", pw,
                  "--carrier", "image-adaptive")
    assert rc == 0


# ── CLI: --json output ────────────────────────────────────────────────────────

def test_cli_json_output(tmp_path, capsys):
    img = _rand_image()
    cover = str(tmp_path / "cover.png")
    out = str(tmp_path / "stego.png")
    img.save(cover)
    pw = "json-test-pw!"

    _run_cli("encode", "--image", cover, "--text", "json test",
             "--password", pw, "--output", out, "--json")

    rc = _run_cli("decode", "--image", out, "--password", pw, "--json")
    assert rc == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out.strip().split("\n")[-1])
    assert data["status"] == "success"
    assert data["text"] == "json test"


# ── CLI: wrong password exit code ────────────────────────────────────────────

def test_cli_wrong_password_exit_code(tmp_path):
    img = _rand_image()
    cover = str(tmp_path / "cover.png")
    out = str(tmp_path / "stego.png")
    img.save(cover)

    _run_cli("encode", "--image", cover, "--text", "secret",
             "--password", "correct!", "--output", out)
    rc = _run_cli("decode", "--image", out, "--password", "WRONG!")
    assert rc == 1  # EXIT_WRONG_PASSWORD


# ── CLI: png-chunk carrier ────────────────────────────────────────────────────

def test_cli_png_chunk_roundtrip(tmp_path):
    img = _rand_image()
    cover = str(tmp_path / "cover.png")
    out = str(tmp_path / "chunk.png")
    img.save(cover)
    pw = "chunk-pw-2026!"

    rc = _run_cli("encode", "--image", cover, "--text", "chunk payload",
                  "--password", pw, "--carrier", "png-chunk", "--output", out)
    assert rc == 0

    rc = _run_cli("decode", "--image", out, "--password", pw,
                  "--carrier", "png-chunk")
    assert rc == 0


# ── CLI: audio carrier ────────────────────────────────────────────────────────

def test_cli_audio_roundtrip(tmp_path):
    wav_in = str(tmp_path / "cover.wav")
    wav_out = str(tmp_path / "stego.wav")
    _make_wav(wav_in)
    pw = "audio-pw-2026!"

    rc = _run_cli("encode", "--audio", wav_in, "--text", "audio payload",
                  "--password", pw, "--carrier", "audio", "--output", wav_out)
    assert rc == 0

    rc = _run_cli("decode", "--audio", wav_out, "--password", pw,
                  "--carrier", "audio")
    assert rc == 0


# ── PersistentHistory ─────────────────────────────────────────────────────────

def test_persistent_history_roundtrip(tmp_path, monkeypatch):
    """History persists to disk and loads on the next instantiation."""
    monkeypatch.setattr(PersistentHistory, "HISTORY_DIR", tmp_path)
    monkeypatch.setattr(PersistentHistory, "HISTORY_PATH", tmp_path / "history.json")
    PersistentHistory._entries = None  # reset in-memory cache

    PersistentHistory.add("encode", "test encode", True, 42.0)
    PersistentHistory.add("decode", "test decode", False, 15.5, "wrong pw")
    assert PersistentHistory.count() == 2

    # Simulate a fresh load
    PersistentHistory._entries = None
    entries = PersistentHistory.all()
    assert len(entries) == 2
    assert entries[0]["op_type"] == "encode"
    assert entries[1]["success"] is False
    assert entries[1]["reason"] == "wrong pw"


def test_persistent_history_clear(tmp_path, monkeypatch):
    monkeypatch.setattr(PersistentHistory, "HISTORY_DIR", tmp_path)
    monkeypatch.setattr(PersistentHistory, "HISTORY_PATH", tmp_path / "history.json")
    PersistentHistory._entries = None

    PersistentHistory.add("encode", "will be cleared", True, 1.0)
    PersistentHistory.clear()
    assert PersistentHistory.count() == 0

    PersistentHistory._entries = None  # reload
    assert PersistentHistory.count() == 0


def test_persistent_history_cap(tmp_path, monkeypatch):
    """History never exceeds MAX_ENTRIES."""
    monkeypatch.setattr(PersistentHistory, "HISTORY_DIR", tmp_path)
    monkeypatch.setattr(PersistentHistory, "HISTORY_PATH", tmp_path / "history.json")
    monkeypatch.setattr(PersistentHistory, "MAX_ENTRIES", 5)
    PersistentHistory._entries = None

    for i in range(8):
        PersistentHistory.add("encode", f"op {i}", True, float(i))

    assert PersistentHistory.count() == 5
    # Should be the last 5
    assert PersistentHistory.all()[0]["description"] == "op 3"


# ── VaultEngine: no deprecated-API warnings ──────────────────────────────────

def test_vault_engine_no_deprecation_warnings():
    """VaultEngine must not emit any Pillow DeprecationWarning (getdata/putdata)."""
    img = _rand_image(128, 128, seed=7)
    decoy_payload = FilePacker.pack_text("decoy message")
    real_payload = FilePacker.pack_text("real message")
    pw_outer = "decoy-pw!"
    pw_real = "real-pw!"

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        stego = VaultEngine.encode(img, decoy_payload, real_payload, pw_outer, pw_real)
        dec_outer = VaultEngine.decode_outer(stego, pw_outer)
        dec_inner = VaultEngine.decode_inner(stego, pw_real)

    pillow_deprecations = [
        x for x in w
        if issubclass(x.category, DeprecationWarning)
        and "getdata" in str(x.message).lower()
    ]
    assert not pillow_deprecations, (
        f"VaultEngine still uses deprecated Pillow API: {pillow_deprecations}"
    )
    assert FilePacker.unpack(dec_outer)["text"] == "decoy message"
    assert FilePacker.unpack(dec_inner)["text"] == "real message"


# ── EmailSender: subject defaults ────────────────────────────────────────────

def test_email_sender_default_subject(tmp_path):
    """Default subject must NOT contain 'StegoXpress' or reveal the tool."""
    img = _rand_image()
    img_path = str(tmp_path / "img.png")
    img.save(img_path)

    sender = EmailSender("gmail")
    msg = sender._build_message("from@example.com", "to@example.com",
                                img_path, "", "")
    subject = msg["Subject"]
    assert "stegoxpress" not in subject.lower(), (
        f"Default subject reveals tool name: {subject!r}"
    )
    assert subject.strip() != "", "Subject must not be empty"


def test_email_sender_custom_subject(tmp_path):
    """Custom subject must be passed through unchanged."""
    img = _rand_image()
    img_path = str(tmp_path / "img.png")
    img.save(img_path)

    sender = EmailSender("gmail")
    msg = sender._build_message("from@example.com", "to@example.com",
                                img_path, "", "Vacation photos")
    assert msg["Subject"] == "Vacation photos"


def test_email_sender_hint_in_body(tmp_path):
    """Hint message must appear in the email body."""
    img = _rand_image()
    img_path = str(tmp_path / "img.png")
    img.save(img_path)

    sender = EmailSender("gmail")
    msg = sender._build_message("from@example.com", "to@example.com",
                                img_path, "Check the blue folder", "")
    body = msg.get_body().get_content()
    assert "Check the blue folder" in body


# ── Version command ───────────────────────────────────────────────────────────

def test_cli_version_command():
    rc = _run_cli("version")
    assert rc == 0


# ── Vault CLI ────────────────────────────────────────────────────────────────

def test_cli_vault_encode_decode_outer(tmp_path):
    img = _rand_image(128, 128, seed=10)
    cover = str(tmp_path / "cover.png")
    out = str(tmp_path / "vault.png")
    img.save(cover)
    pw_outer, pw_real = "outer-pw!", "real-pw!"

    rc = _run_cli("vault", "encode",
                  "--image", cover,
                  "--decoy", "decoy text",
                  "--real", "real secret",
                  "--outer-password", pw_outer,
                  "--real-password", pw_real,
                  "--output", out)
    assert rc == 0

    rc = _run_cli("vault", "decode", "--image", out, "--password", pw_outer)
    assert rc == 0


def test_cli_vault_decode_inner(tmp_path, capsys):
    img = _rand_image(128, 128, seed=11)
    cover = str(tmp_path / "cover.png")
    out = str(tmp_path / "vault.png")
    img.save(cover)
    pw_outer, pw_real = "outer-2!", "real-2!"

    _run_cli("vault", "encode",
             "--image", cover,
             "--decoy", "nothing here",
             "--real", "top secret",
             "--outer-password", pw_outer,
             "--real-password", pw_real,
             "--output", out)
    capsys.readouterr()   # discard encode stdout before checking decode

    _run_cli("vault", "decode", "--image", out, "--password", pw_real, "--json")
    captured = capsys.readouterr()
    data = json.loads(captured.out.strip())
    assert data["status"] == "success"
    assert data["zone"] == "inner"
    assert data["text"] == "top secret"


def test_cli_vault_wrong_password_fails(tmp_path):
    img = _rand_image(128, 128, seed=12)
    cover = str(tmp_path / "cover.png")
    out = str(tmp_path / "vault.png")
    img.save(cover)

    _run_cli("vault", "encode",
             "--image", cover, "--decoy", "d", "--real", "r",
             "--outer-password", "opw!", "--real-password", "rpw!",
             "--output", out)

    rc = _run_cli("vault", "decode", "--image", out, "--password", "WRONG!")
    assert rc == 1  # EXIT_WRONG_PASSWORD


# ── Shield CLI ───────────────────────────────────────────────────────────────

def test_cli_shield_encode_decode(tmp_path):
    covers = []
    for i in range(3):
        img = _rand_image(256, 256, seed=20 + i)
        p = str(tmp_path / f"cover_{i}.png")
        img.save(p)
        covers.append(p)

    pw = "shield-cli-pw!"
    rc = _run_cli("shield", "encode",
                  "--covers", *covers,
                  "--shares", "3", "--threshold", "2",
                  "--text", "shield secret",
                  "--password", pw,
                  "--output-dir", str(tmp_path),
                  "--output-prefix", "sh")
    assert rc == 0

    shares = [str(tmp_path / f"sh_0{i}.png") for i in (1, 2)]
    rc = _run_cli("shield", "decode",
                  "--images", *shares,
                  "--password", pw)
    assert rc == 0


def test_cli_shield_threshold_enforcement(tmp_path, capsys):
    """Providing fewer than K shares must return an error."""
    covers = []
    for i in range(3):
        img = _rand_image(256, 256, seed=30 + i)
        p = str(tmp_path / f"cover_{i}.png")
        img.save(p)
        covers.append(p)

    pw = "shield-thresh-pw!"
    _run_cli("shield", "encode",
             "--covers", *covers,
             "--shares", "3", "--threshold", "2",
             "--text", "secret",
             "--password", pw,
             "--output-dir", str(tmp_path),
             "--output-prefix", "t")

    # Provide only 1 share (threshold=2) — must fail
    rc = _run_cli("shield", "decode",
                  "--images", str(tmp_path / "t_01.png"),
                  "--password", pw)
    assert rc != 0  # should be EXIT_WRONG_PASSWORD


# ── Info subcommand ───────────────────────────────────────────────────────────

def test_cli_info_image_json(tmp_path, capsys):
    img = _rand_image(256, 256, seed=40)
    p = str(tmp_path / "img.png")
    img.save(p)

    rc = _run_cli("info", "--image", p, "--json")
    assert rc == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out.strip())
    assert data["width"] == 256
    assert data["height"] == 256
    assert "carrier_lsb_capacity_bytes" in data
    assert "kdf_default" in data


def test_cli_info_audio_json(tmp_path, capsys):
    wav = str(tmp_path / "cover.wav")
    _make_wav(wav)

    rc = _run_cli("info", "--audio", wav, "--json")
    assert rc == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out.strip())
    assert data["format"] == "WAV"
    assert "carrier_audio_lsb_capacity_bytes" in data


# ── Heatmap subcommand ────────────────────────────────────────────────────────

def test_cli_heatmap_creates_png(tmp_path):
    img = _rand_image(64, 64, seed=50)
    src = str(tmp_path / "src.png")
    out = str(tmp_path / "heatmap.png")
    img.save(src)

    rc = _run_cli("heatmap", "--image", src, "--output", out)
    assert rc == 0
    assert os.path.exists(out)
    with Image.open(out) as hm:
        assert hm.size == (64, 64)
        assert hm.mode == "RGB"


# ── Steganalysis subcommand ───────────────────────────────────────────────────

def test_cli_steganalysis_identical_score_near_zero(tmp_path, capsys):
    """Comparing an image to itself should yield a score very close to 0."""
    img = _rand_image(64, 64, seed=60)
    p = str(tmp_path / "img.png")
    img.save(p)

    rc = _run_cli("steganalysis", "--original", p, "--stego", p, "--json")
    assert rc == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out.strip())
    assert data["score"] < 0.05, f"Self-compare score too high: {data['score']}"


def test_cli_steganalysis_detects_heavy_payload(tmp_path, capsys):
    """Heavy LSB encoding in a smooth (low-entropy) image must yield a high RS score."""
    # Use a smooth gradient image: LSBs are all 0 → encoding makes them random → high score
    w, h = 256, 256
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(h):
        for x in range(w):
            arr[y, x] = [x, y, (x + y) // 2]  # smooth gradient
    img = Image.fromarray(arr, "RGB")
    original = str(tmp_path / "original.png")
    stego_out = str(tmp_path / "stego.png")
    img.save(original)

    pw = "steg-score-pw!"
    # Pack the full capacity with encrypted data
    from core.crypto_engine import CryptoEngine
    from core.lsb_engine import LSBEngine
    capacity = LSBEngine.capacity_bytes(img)
    payload = bytes(range(256)) * (capacity // 256)
    enc = CryptoEngine.encrypt(payload, pw, use_argon2=False)
    stego_img = LSBEngine.encode(img, enc)
    stego_img.save(stego_out)

    rc = _run_cli("steganalysis", "--original", original, "--stego", stego_out, "--json")
    assert rc == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out.strip())
    assert data["score"] > 0.3, f"Expected high steg score on smooth image, got {data['score']}"


# ── CryptoEngine v3 (Argon2id) ───────────────────────────────────────────────

def test_crypto_v3_argon2id_roundtrip():
    from core.crypto_engine import CryptoEngine
    if not CryptoEngine.argon2_available():
        pytest.skip("argon2-cffi not installed")

    plaintext = b"argon2id test payload"
    bundle = CryptoEngine.encrypt(plaintext, "strong-pw!", use_argon2=True)
    assert bundle[:4] == b"SXP3", "Expected v3 magic"
    recovered = CryptoEngine.decrypt(bundle, "strong-pw!")
    assert recovered == plaintext


def test_crypto_v3_wrong_password_fails():
    from core.crypto_engine import CryptoEngine
    if not CryptoEngine.argon2_available():
        pytest.skip("argon2-cffi not installed")

    bundle = CryptoEngine.encrypt(b"secret", "correct-pw!", use_argon2=True)
    with pytest.raises(ValueError):
        CryptoEngine.decrypt(bundle, "wrong-pw!")


def test_crypto_v3_force_pbkdf2_fallback():
    """use_argon2=False must produce v2 (PBKDF2) bundle even if argon2-cffi is installed."""
    from core.crypto_engine import CryptoEngine
    bundle = CryptoEngine.encrypt(b"pbkdf2 test", "pw!", use_argon2=False)
    assert bundle[:4] == b"SXP2", f"Expected SXP2 magic, got {bundle[:4]}"
    assert CryptoEngine.decrypt(bundle, "pw!") == b"pbkdf2 test"
