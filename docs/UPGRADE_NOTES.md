# StegoXpress v2 — Upgrade Notes

v2.0.0 ships hardened, drop-in replacements for the security-critical parts of
StegoXpress, plus packaging and CI scaffolding. Everything has been executed and
validated end-to-end (`tests/test_upgrade.py` — 8/8 groups passing).

## What changed (and why it matters)

Security reviewers will look for exactly these things. Each fix below turns a
potential deal-breaker into a selling point.

| Audit ID | Severity | Fix shipped in v2 |
|----------|----------|-----------------------------|
| V1 | Critical | Removed plaintext-password QR; added `generate_one_time_token()` |
| V2 | Critical | Seal key now salted PBKDF2 (was unsalted SHA-256) |
| V3 | Medium | Adaptive LSB made deterministic (LSB-masked entropy) |
| V6 | Medium | Decompression-bomb guard (`MAX_IMAGE_PIXELS`) |
| V7 | Low | Shamir rewritten to standard GF(2^8) |
| V8 | Low | Vectorized entropy/heatmap (NumPy) |
| V9 | Low | CI, pip-audit, pyproject, tests, honest SECURITY.md |
| V4, V5 | Medium | Documented honestly (deniability/self-destruct are best-effort) |

## Key files

```
core/crypto_engine.py     # versioned AES-256-GCM bundle, header as AAD, 600k PBKDF2, v1 compat
core/shamir_engine.py     # GF(2^8) secret sharing; shares == secret length
core/lsb_engine.py        # deterministic adaptive mode + vectorized entropy/heatmap + DoS guard
core/file_packer.py       # salted-PBKDF2 HMAC seals
core/vault_engine.py      # unchanged API; honest deniability docstring
core/shield_engine.py     # unchanged API; benefits from smaller shares
transport/key_manager.py  # secure token (no password leak), optional QR
tests/test_upgrade.py     # end-to-end validation suite
pyproject.toml            # deps + dev/qr extras
.github/workflows/ci.yml  # ruff + mypy + pytest/coverage + pip-audit
SECURITY.md  CHANGELOG.md
```

## Breaking API change

- `KeyManager.generate_share_link(...)` was **removed** (it leaked the cleartext
  password to disk). Use `KeyManager.generate_one_time_token()` instead.

## Backward compatibility

- Old (v1) encrypted images still **decrypt** — the crypto engine detects the
  legacy format and uses 480k iterations for those.
- Adaptive-mode images created by v1 are NOT compatible (the magic changed from
  `ADAP` to `ADA2`) because the old format could silently corrupt. Re-encode
  any adaptive images you want to keep.
- Shamir shares created by v1 are NOT compatible (field changed to GF(2^8)).
  Re-split any secrets you need to keep.

## Developer setup

```bash
pip install -e ".[dev]"
pytest
```
