import os
import pytest
from PIL import Image
from core.crypto_engine import CryptoEngine
from core.file_packer import FilePacker
from core.vault_engine import VaultEngine


def _big_img():
    return Image.new("RGB", (400, 400), "white")


def test_vault_encode_decode_outer():
    img = _big_img()
    outer, inner = FilePacker.pack_vault("decoy message", "TOP SECRET")
    stego = VaultEngine.encode(img, outer, inner, "passA", "passB")
    result = FilePacker.unpack(VaultEngine.decode_outer(stego, "passA"))
    assert result["type"] == "vault_outer"
    assert result["text"] == "decoy message"


def test_vault_encode_decode_inner():
    img = _big_img()
    outer, inner = FilePacker.pack_vault("decoy message", "TOP SECRET")
    stego = VaultEngine.encode(img, outer, inner, "passA", "passB")
    result = FilePacker.unpack(VaultEngine.decode_inner(stego, "passB"))
    assert result["type"] == "vault_inner"
    assert result["text"] == "TOP SECRET"


def test_vault_wrong_password_outer():
    img = _big_img()
    outer, inner = FilePacker.pack_vault("decoy", "real")
    stego = VaultEngine.encode(img, outer, inner, "passA", "passB")
    with pytest.raises(ValueError, match="[Ww]rong password"):
        VaultEngine.decode_outer(stego, "wrong")


def test_vault_wrong_password_inner():
    img = _big_img()
    outer, inner = FilePacker.pack_vault("decoy", "real")
    stego = VaultEngine.encode(img, outer, inner, "passA", "passB")
    with pytest.raises(ValueError, match="[Ww]rong password"):
        VaultEngine.decode_inner(stego, "wrong")


def test_vault_outer_password_cannot_decode_inner():
    img = _big_img()
    outer, inner = FilePacker.pack_vault("decoy", "real")
    stego = VaultEngine.encode(img, outer, inner, "passA", "passB")
    with pytest.raises(ValueError):
        VaultEngine.decode_inner(stego, "passA")


def test_vault_capacity_error():
    tiny = Image.new("RGB", (20, 20), "white")
    large = os.urandom(5000)
    with pytest.raises(ValueError, match="[Tt]oo large"):
        VaultEngine.encode(tiny, large, large, "a", "b")


def test_vault_capacity_helpers():
    img = _big_img()
    assert VaultEngine.capacity_outer_bytes(img) > 0
    assert VaultEngine.capacity_inner_bytes(img) > 0


def test_vault_pack_types():
    outer, inner = FilePacker.pack_vault("decoy", "real")
    assert outer[0] == FilePacker.VAULT_OUTER_TYPE
    assert inner[0] == FilePacker.VAULT_INNER_TYPE
    assert FilePacker.is_vault_outer(FilePacker.unpack(outer))
    assert FilePacker.is_vault_inner(FilePacker.unpack(inner))
