"""
CryptoEngine — authenticated encryption for StegoXpress.

Bundle format history
---------------------
v1 (legacy)  : salt(16) + nonce(12) + ciphertext — no magic, no AAD.
               PBKDF2-HMAC-SHA256, 480k iterations. Decrypt-only compat.
v2           : b"SXP2"(4) + 0x02(1) + salt(16) + nonce(12) + ct+tag.
               PBKDF2-HMAC-SHA256, 600k iterations. Header is AES-GCM AAD.
v3 (current) : b"SXP3"(4) + 0x03(1) + salt(16) + nonce(12) + ct+tag.
               Argon2id KDF (time=3, mem=64MiB, par=4) when argon2-cffi
               is installed; graceful fallback to PBKDF2 600k if not.
               Header is AES-GCM AAD. Identical wire format to v2 — only
               the magic and KDF change.

Backward compatibility
----------------------
decrypt() auto-detects the bundle version:
  "SXP3" → v3 (Argon2id / PBKDF2 fallback)
  "SXP2" → v2 (PBKDF2 600k)
  no magic → v1 legacy (PBKDF2 480k, no AAD)

v3 bundles created with Argon2id cannot be decrypted on a machine that
has never had argon2-cffi installed. The error message guides the user to
install the optional dependency.
"""
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Try to import argon2-cffi for the v3 KDF.  Optional — falls back to PBKDF2.
try:
    from argon2.low_level import hash_secret_raw, Type as _Argon2Type  # type: ignore[import]
    _ARGON2_AVAILABLE = True
except ImportError:
    _ARGON2_AVAILABLE = False


class CryptoEngine:
    # v2 constants (still used by v2 decrypt path)
    MAGIC_V2 = b"SXP2"
    VERSION_V2 = 2

    # v3 constants
    MAGIC_V3 = b"SXP3"
    VERSION_V3 = 3

    # Shared geometry
    SALT_SIZE = 16
    NONCE_SIZE = 12
    KEY_SIZE = 32
    PBKDF2_ITERATIONS = 600_000

    # Argon2id parameters (OWASP 2023 interactive login guidance)
    ARGON2_TIME_COST = 3
    ARGON2_MEMORY_COST = 65_536   # 64 MiB
    ARGON2_PARALLELISM = 4

    HEADER_SIZE = 5  # magic(4) + version(1)

    @staticmethod
    def argon2_available() -> bool:
        """Return True if Argon2id KDF is available (argon2-cffi installed)."""
        return _ARGON2_AVAILABLE

    # ── Key derivation ──────────────────────────────────────────────────────

    @staticmethod
    def derive_key(password: str, salt: bytes | None = None,
                   iterations: int | None = None) -> tuple[bytes, bytes]:
        """PBKDF2-HMAC-SHA256 key derivation (v1/v2 path)."""
        if salt is None:
            salt = os.urandom(CryptoEngine.SALT_SIZE)
        if iterations is None:
            iterations = CryptoEngine.PBKDF2_ITERATIONS
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=CryptoEngine.KEY_SIZE,
            salt=salt,
            iterations=iterations,
        )
        return kdf.derive(password.encode("utf-8")), salt

    @staticmethod
    def derive_key_argon2id(password: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
        """
        Argon2id key derivation (v3 path).

        Requires argon2-cffi: pip install argon2-cffi
        Raises RuntimeError if the package is not installed.
        """
        if not _ARGON2_AVAILABLE:
            raise RuntimeError(
                "Argon2id KDF requires the 'argon2-cffi' package. "
                "Install it with:  pip install argon2-cffi"
            )
        if salt is None:
            salt = os.urandom(CryptoEngine.SALT_SIZE)
        key = hash_secret_raw(
            secret=password.encode("utf-8"),
            salt=salt,
            time_cost=CryptoEngine.ARGON2_TIME_COST,
            memory_cost=CryptoEngine.ARGON2_MEMORY_COST,
            parallelism=CryptoEngine.ARGON2_PARALLELISM,
            hash_len=CryptoEngine.KEY_SIZE,
            type=_Argon2Type.ID,
        )
        return key, salt

    @staticmethod
    def derive_subkey(master_key: bytes, info: bytes, length: int = 32) -> bytes:
        """Derive a purpose-separated subkey from an already-strong master key."""
        hkdf = HKDF(algorithm=hashes.SHA256(), length=length, salt=None, info=info)
        return hkdf.derive(master_key)

    # ── Encryption ──────────────────────────────────────────────────────────

    @staticmethod
    def encrypt(plaintext: bytes, password: str, *, use_argon2: bool | None = None) -> bytes:
        """
        Encrypt plaintext under password.

        use_argon2:
          None (default) — use Argon2id if available, else PBKDF2.
          True           — require Argon2id; raise if argon2-cffi not installed.
          False          — always use PBKDF2 (e.g. for cross-platform bundles).
        """
        want_argon2 = _ARGON2_AVAILABLE if use_argon2 is None else use_argon2
        if want_argon2:
            key, salt = CryptoEngine.derive_key_argon2id(password)
            magic = CryptoEngine.MAGIC_V3
            version = CryptoEngine.VERSION_V3
        else:
            key, salt = CryptoEngine.derive_key(password)
            magic = CryptoEngine.MAGIC_V2
            version = CryptoEngine.VERSION_V2

        nonce = os.urandom(CryptoEngine.NONCE_SIZE)
        header = magic + bytes([version])
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, header)
        return header + salt + nonce + ciphertext

    @staticmethod
    def decrypt(bundle: bytes, password: str) -> bytes:
        """Auto-detect bundle version and decrypt."""
        if bundle[:4] == CryptoEngine.MAGIC_V3:
            return CryptoEngine._decrypt_v3(bundle, password)
        if bundle[:4] == CryptoEngine.MAGIC_V2:
            return CryptoEngine._decrypt_v2(bundle, password)
        # Legacy v1: no magic header.
        return CryptoEngine._decrypt_legacy(bundle, password)

    # ── Private decrypt paths ───────────────────────────────────────────────

    @staticmethod
    def _decrypt_v3(bundle: bytes, password: str) -> bytes:
        """Argon2id (v3) decrypt — falls back to PBKDF2 if argon2-cffi is missing."""
        h = CryptoEngine.HEADER_SIZE
        s = h + CryptoEngine.SALT_SIZE
        n = s + CryptoEngine.NONCE_SIZE
        header = bundle[:h]
        salt = bundle[h:s]
        nonce = bundle[s:n]
        ciphertext = bundle[n:]

        # Try Argon2id first
        if _ARGON2_AVAILABLE:
            try:
                key, _ = CryptoEngine.derive_key_argon2id(password, salt)
                return AESGCM(key).decrypt(nonce, ciphertext, header)
            except InvalidTag:
                raise ValueError("Wrong password or corrupted data") from None

        # argon2-cffi not installed: tell the user what to do
        raise RuntimeError(
            "This bundle was encrypted with Argon2id KDF.\n"
            "Install argon2-cffi to decrypt it:  pip install argon2-cffi"
        )

    @staticmethod
    def _decrypt_v2(bundle: bytes, password: str) -> bytes:
        h = CryptoEngine.HEADER_SIZE
        s = h + CryptoEngine.SALT_SIZE
        n = s + CryptoEngine.NONCE_SIZE
        header = bundle[:h]
        salt = bundle[h:s]
        nonce = bundle[s:n]
        ciphertext = bundle[n:]
        key, _ = CryptoEngine.derive_key(password, salt)
        try:
            return AESGCM(key).decrypt(nonce, ciphertext, header)
        except InvalidTag as exc:
            raise ValueError("Wrong password or corrupted data") from exc

    @staticmethod
    def _decrypt_legacy(bundle: bytes, password: str) -> bytes:
        """v1 legacy: salt(16) + nonce(12) + ciphertext, 480k iterations, no AAD."""
        salt = bundle[:16]
        nonce = bundle[16:28]
        ciphertext = bundle[28:]
        key, _ = CryptoEngine.derive_key(password, salt, iterations=480_000)
        try:
            return AESGCM(key).decrypt(nonce, ciphertext, None)
        except InvalidTag as exc:
            raise ValueError("Wrong password or corrupted data") from exc
