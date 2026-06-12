"""
ShamirEngine — Shamir's Secret Sharing over GF(2**8) (the standard AES field).

v2 changes (fixes audit finding V7):
- Moved from the non-standard GF(257) (which needed 2 bytes per secret byte and
  introduced modulo bias) to the standard GF(2**8) with reduction polynomial
  0x11B. Each share is now exactly the same length as the secret.
- Coefficients are sampled uniformly from full bytes (no modulo bias).

Share wire format is unchanged at the call-site level: split() returns a list of
`n` bytes objects; reconstruct() takes a list of (x_1based, share_bytes) tuples.
"""
import os


class _GF256:
    """Precomputed log/antilog tables for GF(2**8), generator 0x03."""
    EXP = [0] * 512
    LOG = [0] * 256

    @classmethod
    def _build(cls):
        x = 1
        for i in range(255):
            cls.EXP[i] = x
            cls.LOG[x] = i
            x ^= cls._xtime(x)  # multiply by generator 0x03 == x*2 ^ x
        for i in range(255, 512):
            cls.EXP[i] = cls.EXP[i - 255]

    @staticmethod
    def _xtime(a: int) -> int:
        a <<= 1
        if a & 0x100:
            a ^= 0x11B
        return a & 0xFF

    @classmethod
    def mul(cls, a: int, b: int) -> int:
        if a == 0 or b == 0:
            return 0
        return cls.EXP[cls.LOG[a] + cls.LOG[b]]

    @classmethod
    def inv(cls, a: int) -> int:
        if a == 0:
            raise ZeroDivisionError("No inverse for 0 in GF(256)")
        return cls.EXP[255 - cls.LOG[a]]


_GF256._build()


class ShamirEngine:
    @staticmethod
    def split(secret: bytes, n: int, k: int) -> list:
        """Split secret into n shares; any k reconstruct it. Each share == len(secret)."""
        if not (2 <= k <= n <= 255):
            raise ValueError(f"Need 2 <= k <= n <= 255; got k={k}, n={n}")

        shares = [bytearray() for _ in range(n)]
        for byte_val in secret:
            coeffs = [byte_val] + [b for b in os.urandom(k - 1)]
            for share_idx in range(n):
                x = share_idx + 1  # x in 1..n; x=0 is the secret
                y = 0
                # Horner's method in GF(256)
                for coeff in reversed(coeffs):
                    y = _GF256.mul(y, x) ^ coeff
                shares[share_idx].append(y)
        return [bytes(s) for s in shares]

    @staticmethod
    def reconstruct(shares: list) -> bytes:
        """shares: list of (x_value_1based, share_bytes). Returns the secret."""
        if not shares:
            raise ValueError("No shares provided")
        secret_len = len(shares[0][1])
        result = bytearray()
        for byte_idx in range(secret_len):
            points = [(x_val, share_bytes[byte_idx]) for x_val, share_bytes in shares]
            result.append(ShamirEngine._lagrange_at_zero(points))
        return bytes(result)

    @staticmethod
    def share_size_bytes(secret_bytes: int) -> int:
        """Each share is exactly the secret length in GF(256)."""
        return secret_bytes

    @staticmethod
    def _lagrange_at_zero(points: list) -> int:
        secret = 0
        for i, (xi, yi) in enumerate(points):
            num = 1
            den = 1
            for j, (xj, _) in enumerate(points):
                if i == j:
                    continue
                num = _GF256.mul(num, xj)            # (0 - xj) == xj in GF(256)
                den = _GF256.mul(den, xi ^ xj)       # (xi - xj) == xi ^ xj
            lagrange = _GF256.mul(num, _GF256.inv(den))
            secret ^= _GF256.mul(yi, lagrange)
        return secret
