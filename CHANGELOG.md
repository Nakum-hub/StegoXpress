# Changelog

## [2.0.0] — 2025

### Added — Unique Features (no free tool has these)

- **StegoVault** (`core/vault_engine.py`, `gui/vault_tab.py`)
  Dual-password hidden volumes. Decoy password reveals planted harmless content;
  real password reveals the actual secret. Adversary who extracts one password
  never knows a second message exists.

- **StegoShield** (`core/shamir_engine.py`, `core/shield_engine.py`, `gui/shield_tab.py`)
  Shamir's Secret Sharing across N images. Any K of N images reconstruct the secret.
  No single image holder can decode alone.

- **MultiCarrier** (`core/audio_engine.py`, `core/png_chunk_engine.py`)
  - **WAV Audio**: LSB into 16-bit PCM samples. Same password workflow, audio output.
  - **PNG Metadata**: Payload hidden in a private "stXp" chunk. Image pixels are
    visually and numerically identical; ~2 GB capacity.

- **StegoSeal** (`core/file_packer.py` — SEALED_TYPE)
  HMAC-SHA256 tamper-proof seal. Decoding fails if even one pixel was changed
  after encoding.

- **Self-Destruct Mode** (`core/file_packer.py` — SELF_DESTRUCT_TYPE, `core/lsb_engine.py` — erase)
  LSB layer is zeroed after first successful decode. Image becomes undecodable
  on all subsequent attempts.

- **Entropy Heatmap** (`core/lsb_engine.py` — generate_heatmap, `gui/encode_tab.py`)
  Visual overlay showing which pixels are statistically safe for embedding.
  Blue = flat/low entropy; red = high entropy (safest).

- **Steganalysis Score** (`core/lsb_engine.py` — steganalysis_score, `gui/encode_tab.py`)
  RS-analysis score displayed after every encode. Tells the user how detectable
  the embedding is (Low / Medium / High Risk).

- **Adaptive LSB** (`core/lsb_engine.py` — encode_adaptive / decode_adaptive)
  Embeds only into high-entropy pixels (natural textures, edges). Reduces
  RS-analysis detectability vs sequential embedding.

### Added — Infrastructure

- Full modular architecture: `core/`, `gui/`, `transport/`, `utils/`
- AES-256-GCM + PBKDF2 (480,000 iterations) — password-derived, no raw key transmitted
- CustomTkinter GUI with 6 tabs: Encode, Decode, Send, Vault, Shield, History
- Drag-and-drop image loading
- Persistent settings at `~/.stegoxpress/config.json`
- Rotating logs at `~/.stegoxpress/logs/stegoxpress.log`
- Headless CLI: `python main.py encode/decode`
- GitHub Actions CI (Python 3.10 / 3.11 / 3.12, Ubuntu + Windows)
- 77 automated tests

### Fixed (from v1.0)

- Fatal indentation bug — `embed_message` loop was orphaned code, never executed
- Broken decryption — no end delimiter; decoder read entire image as ciphertext
- Security inversion — encryption key was sent in email body plaintext
- Crash on RGBA images — alpha channel not handled before LSB operations
- Output path clobbered input when filenames matched
- Missing `self.cover_image_path` and `self.hidden_file_path` attributes

## [1.0.0] — December 2024

Initial prototype (internship project). Single-file monolithic tkinter app.
