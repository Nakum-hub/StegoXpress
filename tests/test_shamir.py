import itertools
import os
import pytest
from PIL import Image
from core.shamir_engine import ShamirEngine
from core.shield_engine import ShieldEngine
from core.file_packer import FilePacker


# ── ShamirEngine ─────────────────────────────────────────────────────────────

def test_shamir_split_reconstruct_full_set():
    secret = os.urandom(32)
    shares = ShamirEngine.split(secret, 5, 3)
    assert len(shares) == 5
    subset = [(i + 1, shares[i]) for i in [0, 2, 4]]
    assert ShamirEngine.reconstruct(subset) == secret


def test_shamir_any_k_of_n_combination():
    secret = os.urandom(16)
    shares = ShamirEngine.split(secret, 5, 3)
    for combo in itertools.combinations(range(5), 3):
        subset = [(i + 1, shares[i]) for i in combo]
        assert ShamirEngine.reconstruct(subset) == secret, f"combo {combo} failed"


def test_shamir_exact_k_works():
    secret = b"exactly k shares"
    shares = ShamirEngine.split(secret, 4, 4)
    subset = [(i + 1, shares[i]) for i in range(4)]
    assert ShamirEngine.reconstruct(subset) == secret


def test_shamir_n_equals_k_equals_2():
    secret = os.urandom(8)
    shares = ShamirEngine.split(secret, 2, 2)
    assert ShamirEngine.reconstruct([(1, shares[0]), (2, shares[1])]) == secret


def test_shamir_invalid_params():
    with pytest.raises(ValueError):
        ShamirEngine.split(b"x", 1, 1)   # n < 2
    with pytest.raises(ValueError):
        ShamirEngine.split(b"x", 3, 4)   # k > n
    with pytest.raises(ValueError):
        ShamirEngine.split(b"x", 11, 3)  # n > 10


def test_shamir_share_size():
    secret = os.urandom(20)
    shares = ShamirEngine.split(secret, 3, 2)
    for s in shares:
        assert len(s) == ShamirEngine.share_size_bytes(len(secret))


def test_shamir_empty_secret():
    shares = ShamirEngine.split(b"", 3, 2)
    subset = [(1, shares[0]), (3, shares[2])]
    assert ShamirEngine.reconstruct(subset) == b""


# ── ShieldEngine ─────────────────────────────────────────────────────────────

def _imgs(n, size=300):
    return [Image.new("RGB", (size, size), "white") for _ in range(n)]


def test_shield_encode_decode_any_2_of_3():
    imgs = _imgs(3)
    packed = FilePacker.pack_text("shield test")
    stegos = ShieldEngine.encode_shares(packed, imgs, "pw", n=3, k=2)
    assert len(stegos) == 3
    for combo in itertools.combinations(range(3), 2):
        subset = [(i + 1, stegos[i]) for i in combo]
        result = FilePacker.unpack(ShieldEngine.decode_shares(subset, "pw"))
        assert result["text"] == "shield test"


def test_shield_insufficient_shares_raises():
    imgs = _imgs(3)
    stegos = ShieldEngine.encode_shares(FilePacker.pack_text("x"), imgs, "pw", n=3, k=3)
    with pytest.raises(ValueError, match="Need"):
        ShieldEngine.decode_shares([(1, stegos[0]), (2, stegos[1])], "pw")


def test_shield_wrong_password_raises():
    imgs = _imgs(3)
    stegos = ShieldEngine.encode_shares(FilePacker.pack_text("x"), imgs, "correct", n=3, k=2)
    with pytest.raises(ValueError):
        ShieldEngine.decode_shares([(1, stegos[0]), (2, stegos[1])], "wrong")


def test_shield_min_shares_needed():
    imgs = _imgs(4)
    stegos = ShieldEngine.encode_shares(FilePacker.pack_text("x"), imgs, "pw", n=4, k=3)
    n, k = ShieldEngine.min_shares_needed(stegos[0])
    assert n == 4 and k == 3


def test_shield_wrong_image_count():
    imgs = _imgs(3)
    with pytest.raises(ValueError):
        ShieldEngine.encode_shares(FilePacker.pack_text("x"), imgs, "pw", n=4, k=2)
