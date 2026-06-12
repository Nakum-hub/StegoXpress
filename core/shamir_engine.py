"""
ShamirEngine — Shamir's Secret Sharing over integers mod PRIME=257.
Each share value is stored as 2 bytes (uint16 big-endian) because the
prime 257 > 255, so share values 0..256 need more than one byte.
Each share is therefore 2× the length of the secret.
"""
import os


class ShamirEngine:
    PRIME = 257

    @staticmethod
    def split(secret: bytes, n: int, k: int) -> list:
        """
        Split secret into n shares; any k shares reconstruct it.
        Returns list of n bytes objects, each 2× len(secret).
        """
        if not (2 <= k <= n <= 10):
            raise ValueError(f"Need 2 ≤ k ≤ n ≤ 10; got k={k}, n={n}")

        P = ShamirEngine.PRIME
        shares = [bytearray() for _ in range(n)]

        for byte_val in secret:
            # Polynomial: f(x) = byte_val + c1*x + ... + c_{k-1}*x^{k-1}  mod P
            coeffs = [byte_val] + [int.from_bytes(os.urandom(2), "big") % P for _ in range(k - 1)]

            for share_idx in range(n):
                x = share_idx + 1  # x = 1..n
                y = 0
                for power, coeff in enumerate(coeffs):
                    y = (y + coeff * pow(x, power, P)) % P
                # Store y as 2 bytes big-endian (y can be 0..256)
                shares[share_idx] += y.to_bytes(2, "big")

        return [bytes(s) for s in shares]

    @staticmethod
    def reconstruct(shares: list) -> bytes:
        """
        shares: list of (x_value_1based, share_bytes) tuples.
        Returns the reconstructed secret bytes.
        """
        if not shares:
            raise ValueError("No shares provided")

        k = len(shares)
        share_len = len(shares[0][1])  # bytes per share
        secret_len = share_len // 2    # each secret byte → 2 share bytes

        P = ShamirEngine.PRIME
        result = bytearray()

        for byte_idx in range(secret_len):
            # Extract the y-value for this byte position from each share
            points = []
            for x_val, share_bytes in shares:
                y = int.from_bytes(share_bytes[byte_idx * 2:byte_idx * 2 + 2], "big")
                points.append((x_val, y))

            recovered = ShamirEngine._lagrange(0, points, P) % 256
            result.append(recovered)

        return bytes(result)

    @staticmethod
    def share_size_bytes(secret_bytes: int) -> int:
        """Each share is 2× the secret length."""
        return secret_bytes * 2

    @staticmethod
    def _lagrange(x: int, points: list, P: int) -> int:
        result = 0
        for i, (xi, yi) in enumerate(points):
            num = yi
            den = 1
            for j, (xj, _) in enumerate(points):
                if i != j:
                    num = (num * ((x - xj) % P)) % P
                    den = (den * ((xi - xj) % P)) % P
            inv_den = pow(den % P, P - 2, P)  # Fermat's little theorem
            result = (result + num * inv_den) % P
        return result
