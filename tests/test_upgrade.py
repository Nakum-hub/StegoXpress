"""
Validation suite for the StegoXpress v2 hardening work.
Run: python -m pytest tests/test_upgrade.py -v   (or: python tests/test_upgrade.py)
"""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.crypto_engine import CryptoEngine
from core.file_packer import FilePacker
from core.lsb_engine import LSBEngine
from core.shamir_engine import ShamirEngine
from core.shield_engine import ShieldEngine
from core.vault_engine import VaultEngine
from transport.key_manager import KeyManager


def _rand_image(w=96, h=96, seed=0):
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)
    return Image.fromarray(arr, "RGB")


def test_crypto_roundtrip_and_tamper():
    ct = CryptoEngine.encrypt(b"hello world", "correct horse")
    assert CryptoEngine.decrypt(ct, "correct horse") == b"hello world"
    try:
        CryptoEngine.decrypt(ct, "wrong")
        raise AssertionError("wrong password should fail")
    except ValueError:
        pass
    tampered = bytearray(ct)
    tampered[-1] ^= 0x01
    try:
        CryptoEngine.decrypt(bytes(tampered), "correct horse")
        raise AssertionError("tamper should fail")
    except ValueError:
        pass
    print("crypto: roundtrip + wrong-pw + tamper OK")


def test_shamir_gf256():
    secret = os.urandom(40)
    for n, k in [(3, 2), (5, 3), (6, 6), (10, 4)]:
        shares = ShamirEngine.split(secret, n, k)
        assert all(len(s) == len(secret) for s in shares), "share size must equal secret"
        # every combination of exactly k shares reconstructs
        import itertools
        idxs = list(range(n))
        for combo in itertools.combinations(idxs, k):
            subset = [(i + 1, shares[i]) for i in combo]
            assert ShamirEngine.reconstruct(subset) == secret, (n, k, combo)
    print("shamir GF(256): all k-of-n combinations reconstruct OK")


def test_standard_lsb():
    img = _rand_image(seed=1)
    payload = os.urandom(300)
    stego = LSBEngine.encode(img, payload)
    assert LSBEngine.decode(stego) == payload
    print("standard LSB: roundtrip OK")


def test_adaptive_lsb_determinism():
    # Run many random images/payloads; previously this could silently corrupt.
    for seed in range(25):
        img = _rand_image(seed=seed + 10)
        payload = os.urandom(60)
        stego = LSBEngine.encode_adaptive(img, payload)
        out = LSBEngine.decode_adaptive(stego)
        assert out == payload, f"adaptive mismatch at seed {seed}"
    print("adaptive LSB: 25/25 deterministic roundtrips OK")


def test_file_packer_seal():
    sealed = FilePacker.pack_text_sealed("top secret", "pw-123456789")
    assert FilePacker.is_sealed(sealed)
    res = FilePacker.verify_and_unpack_sealed(sealed, "pw-123456789")
    assert res["text"] == "top secret"
    # wrong password fails
    try:
        FilePacker.verify_and_unpack_sealed(sealed, "nope")
        raise AssertionError("wrong seal pw should fail")
    except ValueError:
        pass
    # tamper fails
    t = bytearray(sealed)
    t[5] ^= 0x01
    try:
        FilePacker.verify_and_unpack_sealed(bytes(t), "pw-123456789")
        raise AssertionError("tampered seal should fail")
    except ValueError:
        pass
    print("file_packer seal: salted-PBKDF2 seal roundtrip + tamper OK")


def test_vault_roundtrip():
    img = _rand_image(128, 128, seed=99)
    outer, inner = FilePacker.pack_vault("decoy msg", "the real secret")
    stego = VaultEngine.encode(img, outer, inner, "passA", "passB")
    assert FilePacker.unpack(VaultEngine.decode_outer(stego, "passA"))["text"] == "decoy msg"
    assert FilePacker.unpack(VaultEngine.decode_inner(stego, "passB"))["text"] == "the real secret"
    print("vault: dual-password roundtrip OK")


def test_shield_roundtrip():
    covers = [_rand_image(128, 128, seed=s) for s in range(5)]
    payload = b"shared team secret"
    stegos = ShieldEngine.encode_shares(payload, covers, "team-pw", n=5, k=3)
    subset = [(i + 1, stegos[i]) for i in (0, 2, 4)]  # any 3
    assert ShieldEngine.decode_shares(subset, "team-pw") == payload
    print("shield: 3-of-5 reconstruction OK")


def test_key_manager_no_password_leak():
    # The vulnerable generate_share_link must be gone.
    assert not hasattr(KeyManager, "generate_share_link"), "plaintext-password QR must be removed"
    tok = KeyManager.generate_one_time_token()
    assert isinstance(tok, str) and len(tok) >= 24
    print("key_manager: plaintext-password QR removed; secure token OK")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
        except Exception as exc:  # noqa
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}")
    print(f"\n{len(fns) - failed}/{len(fns)} test groups passed")
    sys.exit(1 if failed else 0)
