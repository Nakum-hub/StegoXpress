"""
CryptoEngine — authenticated encryption for StegoXpress.

v2 changes:
- Versioned, self-describing bundle: MAGIC + version + salt + nonce + ciphertext.
- AES-256-GCM with the header bound as Additional Authenticated Data (AAD),
  so the version/magic cannot be tampered with.
- PBKDF2-HMAC-SHA256 raised to 600,000 iterations (OWASP 2023 guidance).
- HKDF helper to derive purpose-specific subkeys (e.g. the HMAC seal key)
  instead of re-hashing the raw password with bare SHA-256.
- Backward-compatible decryption of legacy (v1) bundles that had no header.
"""
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class CryptoEngine:
    MAGIC = b"SXP2"
    VERSION = 2
    SALT_SIZE = 16
    NONCE_SIZE = 12
    KEY_SIZE = 32
    PBKDF2_ITERATIONS = 600_000

    HEADER_SIZE = len(MAGIC) + 1  # magic(4) + version(1)

    # ── Key derivation ──
    @staticmethod
    def derive_key(password: str, salt: bytes = None,
                   iterations: int = None) -> tuple[bytes, bytes]:
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
        key = kdf.derive(password.encode("utf-8"))
        return key, salt

    @staticmethod
    def derive_subkey(master_key: bytes, info: bytes,
                      length: int = 32) -> bytes:
        """Derive a purpose-separated subkey from an already-strong master key."""
        hkdf = HKDF(algorithm=hashes.SHA256(), length=length,
                    salt=None, info=info)
        return hkdf.derive(master_key)

    # ── Encryption ──
    @staticmethod
    def encrypt(plaintext: bytes, password: str) -> bytes:
        key, salt = CryptoEngine.derive_key(password)
        nonce = os.urandom(CryptoEngine.NONCE_SIZE)
        header = CryptoEngine.MAGIC + bytes([CryptoEngine.VERSION])
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, header)
        return header + salt + nonce + ciphertext

    @staticmethod
    def decrypt(bundle: bytes, password: str) -> bytes:
        if bundle[:len(CryptoEngine.MAGIC)] == CryptoEngine.MAGIC:
            return CryptoEngine._decrypt_v2(bundle, password)
        # Legacy v1 bundle: salt(16) + nonce(12) + ciphertext, no AAD.
        return CryptoEngine._decrypt_legacy(bundle, password)

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
        salt = bundle[:16]
        nonce = bundle[16:28]
        ciphertext = bundle[28:]
        # Legacy used 480k iterations.
        key, _ = CryptoEngine.derive_key(password, salt, iterations=480_000)
        try:
            return AESGCM(key).decrypt(nonce, ciphertext, None)
        except InvalidTag as exc:
            raise ValueError("Wrong password or corrupted data") from exc
