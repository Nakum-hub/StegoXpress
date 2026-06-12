"""
ShieldEngine — N-of-K secret sharing across multiple carrier images.
Each image carries one Shamir share. Any K images reconstruct the secret.
"""
import struct
from PIL import Image
from core.crypto_engine import CryptoEngine
from core.lsb_engine import LSBEngine
from core.shamir_engine import ShamirEngine


class ShieldEngine:

    @staticmethod
    def encode_shares(payload: bytes, cover_images: list, password: str,
                      n: int, k: int) -> list:
        """
        Encrypt payload, split into n Shamir shares, encode each into a cover image.
        Returns list of n PIL.Image objects.
        """
        if len(cover_images) != n:
            raise ValueError(f"Expected {n} cover images, got {len(cover_images)}")

        encrypted = CryptoEngine.encrypt(payload, password)
        shares = ShamirEngine.split(encrypted, n, k)

        result = []
        for i, (image, share_data) in enumerate(zip(cover_images, shares)):
            # 3-byte metadata header: total_shares(1) + min_shares(1) + this_share_num(1)
            header = struct.pack(">BBB", n, k, i + 1)
            share_payload = header + share_data
            stego = LSBEngine.encode(image, share_payload)
            result.append(stego)

        return result

    @staticmethod
    def decode_shares(stego_images_with_index: list, password: str) -> bytes:
        """
        stego_images_with_index: list of (original_1based_share_num, PIL.Image).
        Reconstructs the secret if enough shares are provided.
        """
        collected = []
        k_required = None

        for _provided_idx, image in stego_images_with_index:
            raw = LSBEngine.decode(image)
            if len(raw) < 3:
                raise ValueError("Share image missing metadata header")
            n_stored, k_stored, share_num = struct.unpack(">BBB", raw[:3])
            share_data = raw[3:]
            if k_required is None:
                k_required = k_stored
            collected.append((share_num, share_data))

        if k_required is None:
            raise ValueError("No shares found")

        if len(collected) < k_required:
            raise ValueError(
                f"Need {k_required} shares to reconstruct, only have {len(collected)}"
            )

        # Use exactly k_required shares
        subset = collected[:k_required]
        encrypted = ShamirEngine.reconstruct(subset)
        return CryptoEngine.decrypt(encrypted, password)

    @staticmethod
    def min_shares_needed(stego_image: Image.Image) -> tuple:
        """Returns (n_total, k_min) from the image's share header."""
        raw = LSBEngine.decode(stego_image)
        if len(raw) < 3:
            raise ValueError("Not a StegoShield image")
        n, k, _ = struct.unpack(">BBB", raw[:3])
        return n, k
