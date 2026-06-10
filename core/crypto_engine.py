import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class CryptoEngine:
    @staticmethod
    def derive_key(password: str, salt: bytes = None) -> tuple[bytes, bytes]:
        if salt is None:
            salt = os.urandom(16)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        key = kdf.derive(password.encode("utf-8"))
        return key, salt

    @staticmethod
    def encrypt(plaintext: bytes, password: str) -> bytes:
        key, salt = CryptoEngine.derive_key(password)
        nonce = os.urandom(12)
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
        return salt + nonce + ciphertext

    @staticmethod
    def decrypt(ciphertext_bundle: bytes, password: str) -> bytes:
        salt = ciphertext_bundle[:16]
        nonce = ciphertext_bundle[16:28]
        ciphertext = ciphertext_bundle[28:]
        key, _ = CryptoEngine.derive_key(password, salt)

        try:
            return AESGCM(key).decrypt(nonce, ciphertext, None)
        except InvalidTag as exc:
            raise ValueError("Wrong password or corrupted data") from exc
