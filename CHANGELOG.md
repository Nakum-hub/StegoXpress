# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [2.1.0] - 2026-06-23

### Fixed (critical)
- **README/CLI mismatch (was a critical blocker).** README documented `--text`, `STEGO_PASSWORD` env var, `--seal`, `--adaptive` flags that did not exist in the CLI. The CLI has now been rebuilt to match (and exceed) what the README promised.
- **VaultEngine deprecated Pillow API.** `Image.getdata()` / `Image.putdata()` are removed in Pillow 14 (2027-10-15). Replaced with NumPy array operations — same behaviour, no deprecation warnings.
- **conftest.py pip install anti-pattern.** Removed `subprocess.check_call(["pip", "install", "numpy"])` from the test collection hook. Dependencies must be installed before running tests (documented in README).

### Added (CLI)
- `STEGO_PASSWORD` environment variable — avoids exposing the password in shell history and `ps aux`.
- `--text` / `--message` alias — both accepted (README used `--text`; original CLI had only `--message`).
- `--seal` flag — adds HMAC-SHA256 tamper-proof seal to the payload at encode time.
- `--self-destruct` flag — marks payload for local LSB-plane erasure after first decode.
- `--carrier {image-lsb,image-adaptive,png-chunk,audio}` — selects the embedding method. Previously, adaptive, PNG-chunk, and audio carriers were only accessible via the GUI.
- `--verify-seal` flag on decode — verifies the HMAC seal and returns exit code 1 if broken.
- `--json` flag on encode/decode — emits machine-readable JSON for scripting.
- `--save-dir` flag on decode — directory for extracted files.
- `version` subcommand and `--version` flag.
- `--audio` flag on both encode and decode — explicit audio path for the audio carrier.

### Added (infrastructure)
- `utils/history.py` — `PersistentHistory` class: operation log persists to `~/.stegoxpress/history.json` across sessions, capped at 200 entries, never stores passwords or plaintext.
- History tab rewritten to load persisted entries on startup, show record count, and update on clear.
- Email `--subject` field in Send tab; default subject changed from `"StegoXpress — Secure Message"` to the neutral `"Shared image"` (prevents tool identity disclosure in the email header).
- `tests/test_production.py` — 17 new tests: env-var password, CLI seal roundtrip, seal tamper detection, adaptive CLI, JSON output, wrong-password exit code, PNG-chunk CLI, audio CLI, persistent history (roundtrip / clear / cap), VaultEngine no-deprecation-warning check, EmailSender subject and body correctness, version command.
- `pyproject.toml` updated: added `customtkinter`, `tkinterdnd2` to `[project.dependencies]`, added `utils*` to package discovery, added `[project.scripts]` entry point (`stegoxpress = "main:main"`), added `[tool.coverage.run]`.
- CI workflow rebuilt: separate lint, audit, and test jobs; macOS added to matrix; full `requirements.txt` install; CLI smoke tests for standard, seal, and adaptive modes.

### Total tests: 33 (was 16) — all passing on Python 3.10 / 3.11 / 3.12

---

## [2.0.0] - 2026-06-12

### Security (breaking & high-priority fixes)

- **CRITICAL — removed plaintext-password QR sharing (V1).** `KeyManager` previously QR-encoded the raw password into a temp file with `delete=False`, leaving the cleartext secret on disk permanently. Removed entirely and replaced with `generate_one_time_token()`, which produces a high-entropy token that is never the password.
- **CRITICAL — salted KDF for seals (V2).** Seal keys were derived with bare, unsalted SHA-256 of the password, enabling rainbow-table/precomputation attacks. Now uses salted PBKDF2-HMAC-SHA256 (600k iterations); the 16-byte salt is stored with the MAC.
- **Authenticated header (crypto).** The crypto bundle now carries a magic + version byte and binds the full header into AES-GCM as AAD.
- **KDF hardening.** PBKDF2 iterations raised from 480,000 to 600,000.

### Fixed
- **Adaptive LSB corruption (V3).** Entropy is now computed on LSB-masked pixel values, making encode/decode deterministic (validated across 25 randomized roundtrips).
- **Shamir modulo bias (V7).** Replaced GF(257) arithmetic with standard GF(2^8).

### Performance
- **Vectorized entropy & heatmap (V8).** NumPy-vectorized sliding-window entropy.

### Hardening
- **Decompression-bomb guard (V6).** `Image.MAX_IMAGE_PIXELS` capped to ~64MP.

---

## [1.0.0] - 2026-06-10

- Initial release: LSB steganography, AES-256-GCM encryption, vaults, shields, seals, self-destruct, PNG chunk embedding, GUI.
