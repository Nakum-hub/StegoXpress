# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [2.0.0] - 2026-06-12

### Security (breaking & high-priority fixes)

- **CRITICAL — removed plaintext-password QR sharing (V1).** `KeyManager`
  previously QR-encoded the raw password into a temp file with `delete=False`,
  leaving the cleartext secret on disk permanently. Removed entirely and
  replaced with `generate_one_time_token()`, which produces a high-entropy token
  that is never the password.
- **CRITICAL — salted KDF for seals (V2).** Seal keys were derived with bare,
  unsalted SHA-256 of the password, enabling rainbow-table/precomputation
  attacks. Now uses salted PBKDF2-HMAC-SHA256 (600k iterations); the 16-byte
  salt is stored with the MAC.
- **Authenticated header (crypto).** The crypto bundle now carries a magic +
  version byte and binds the full header into AES-GCM as AAD. Bundle layout:
  `SXP2 | version | salt(16) | nonce(12) | ct+tag`. Legacy v1 bundles still
  decrypt.
- **KDF hardening.** PBKDF2 iterations raised from 480,000 to 600,000.

### Fixed

- **Adaptive LSB corruption (V3).** Entropy is now computed on LSB-masked pixel
  values, so the high-entropy pixel set is identical before and after embedding.
  Adaptive encode/decode is now deterministic (validated across 25 randomized
  roundtrips). Adaptive magic bumped to `ADA2`.
- **Shamir modulo bias (V7).** Replaced GF(257) arithmetic (which leaked/relied
  on a 2-byte-per-value workaround and introduced bias) with standard GF(2^8)
  using log/antilog tables. Shares are now exactly the secret length (half the
  previous size).

### Performance

- **Vectorized entropy & heatmap (V8).** Per-pixel Python loops replaced with
  NumPy-vectorized sliding-window entropy, dramatically speeding up adaptive
  mode and heatmap generation on large images.

### Hardening

- **Decompression-bomb guard (V6).** `Image.MAX_IMAGE_PIXELS` capped to ~64MP to
  prevent denial-of-service via maliciously crafted images.

### Added

- `pyproject.toml` with pinned dependencies and `dev`/`qr` extras.
- GitHub Actions CI: ruff, mypy, pytest+coverage across Python 3.10–3.12, and a
  `pip-audit` dependency-vulnerability job.
- `tests/test_upgrade.py` validating crypto, Shamir, LSB (standard + adaptive),
  seals, vault, and shield end-to-end.
- Honest, expanded `SECURITY.md` threat model.

### Documentation

- Softened overstated guarantees around hidden-volume deniability (V4) and
  self-destruct (V5) to match real capabilities.

## [1.0.0] - 2026-06-10

- Initial release: LSB steganography, AES-256-GCM encryption, vaults, shields,
  seals, self-destruct, PNG chunk embedding, GUI.
