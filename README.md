<p align="center">
  <img src="assets/github_banner.png" alt="StegoXpress" width="480"/>
</p>

<h1 align="center">StegoXpress</h1>

<p align="center"><b>Hide AES-256-GCM-encrypted secrets inside ordinary images, WAV audio, and PNG metadata.</b><br/>
Dual-password decoy vaults &middot; N-of-K secret sharing &middot; tamper-evident seals &middot; built-in steganalysis scoring.</p>

---

## Why StegoXpress

Most steganography tools just flip pixel bits. StegoXpress encrypts **first** (AES-256-GCM, salted PBKDF2 with 600,000 iterations) and hides **second**, so even if the hidden data is found, it is useless without the password. On top of that core, it adds features normally found only in research tools:

| Feature | What it does |
|---|---|
| 🖼 **Multi-carrier** | Image LSB, adaptive LSB (high-entropy regions), WAV audio, PNG metadata chunk |
| 🔐 **StegoVault** | Two passwords: one reveals a decoy message, the other reveals the real one |
| 🛡 **StegoShield** | Splits a secret across N images; any K of them reconstruct it (Shamir, GF(2^8)) |
| 📜 **Tamper seal** | HMAC-SHA256 seal (salted PBKDF2 key) proves the payload was not modified |
| 🔥 **Local burn-after-read** | Optionally erases the LSB plane of the working copy after first decode |
| 📊 **Steganalysis score** | Estimates how detectable your stego image is before you send it |
| 🌡 **Entropy heatmap** | Visualizes where data is hidden / where it is safest to hide |
| 💾 **Persistent history** | Operation log survives restarts — stored in `~/.stegoxpress/history.json` |

## Install

```bash
git clone https://github.com/Nakum-hub/StegoXpress.git
cd StegoXpress
pip install -r requirements.txt
```

Python 3.10+ required. For development: `pip install -e ".[dev]"`

## Usage

### GUI

```bash
python main.py
```

A dark-themed desktop app opens with six tabs: **Encode**, **Decode**, **Send** (email the stego image), **Vault**, **Shield**, and **History**.

### CLI

The CLI is designed to be script-friendly and safe for automation.

#### Password security — avoid shell history exposure

```bash
# ✅ Recommended: set as env var (never appears in `ps aux` or shell history)
export STEGO_PASSWORD='my strong passphrase'

# ⚠️  Only when necessary: flag (appears in process listings)
python main.py encode --image cover.png --text "secret" --password "pass" --output out.png
```

#### Encode

```bash
# Hide a text message (LSB, default carrier)
python main.py encode \
  --image cover.png \
  --text "meet at noon" \
  --output secret.png

# Hide a file with a tamper-proof HMAC seal
python main.py encode \
  --image cover.png \
  --file plans.pdf \
  --seal \
  --output secret.png

# Use adaptive LSB (embeds in high-entropy regions — harder to detect)
python main.py encode \
  --image cover.png \
  --text "covert message" \
  --carrier image-adaptive \
  --output secret.png

# Hide in PNG metadata chunk (pixels completely untouched)
python main.py encode \
  --image cover.png \
  --text "invisible" \
  --carrier png-chunk \
  --output secret.png

# Hide in WAV audio
python main.py encode \
  --audio cover.wav \
  --text "audio secret" \
  --carrier audio \
  --output secret.wav

# Mark as self-destruct (LSB plane erased from local copy after first decode)
python main.py encode \
  --image cover.png \
  --text "burn after reading" \
  --self-destruct \
  --output secret.png
```

#### Decode

```bash
# Decode (password from env var)
python main.py decode --image secret.png

# Decode and verify tamper-proof seal
python main.py decode --image secret.png --verify-seal

# Decode adaptive-mode image
python main.py decode --image secret.png --carrier image-adaptive

# Decode PNG chunk carrier
python main.py decode --image secret.png --carrier png-chunk

# Decode audio
python main.py decode --audio secret.wav --carrier audio

# Machine-readable JSON output (for scripts)
python main.py decode --image secret.png --json

# Save extracted file to a specific directory
python main.py decode --image secret.png --save-dir ~/Downloads
```

#### Carrier reference

| `--carrier` value | Carrier | Capacity | Detectability |
|---|---|---|---|
| `image-lsb` *(default)* | Image pixels (LSB) | ~37% of image file size | Moderate — scales with payload |
| `image-adaptive` | Image pixels (high-entropy only) | Less than LSB | Lower — hides where noise already exists |
| `png-chunk` | Private PNG metadata chunk | Up to file size | Trivially visible to chunk-inspection tools (`pngcheck`) |
| `audio` | WAV sample LSBs | ~1 bit per 16-bit sample | Low — inaudible quality loss |

#### Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Wrong password / corrupted / tampered data |
| `2` | Payload too large for carrier |
| `3` | File not found / I/O error |

#### Script example

```bash
#!/usr/bin/env bash
set -euo pipefail

export STEGO_PASSWORD="$(pass show myproject/stego)"  # or any secret manager

# Encode and capture JSON result
result=$(python main.py encode \
  --image cover.png \
  --file report.pdf \
  --seal \
  --output /tmp/stego.png \
  --json)

echo "$result" | python -c "import sys,json; d=json.load(sys.stdin); print(d['output'])"

# Decode in CI, fail fast on wrong password or tamper
python main.py decode --image /tmp/stego.png --verify-seal --json
```

## Honest security model (read this)

Full details in [SECURITY.md](SECURITY.md).

**It protects against:** casual observers; recovery of the secret without the password (AES-256-GCM); silent tampering (authenticated encryption + seals).

**It does NOT protect against:** statistical steganalysis of large payloads (adaptive mode reduces, never eliminates, detectability); a determined forensic analyst examining vault images (hidden-volume deniability is statistical, not absolute); copies you no longer control ("burn-after-read" only erases the local working copy); lossy re-encoding (JPEG/screenshots destroy payloads — use PNG); a compromised endpoint.

## Quality

- CI on Python 3.10–3.12, Linux/Windows/macOS: ruff, mypy, pytest with coverage, pip-audit
- 33 tests covering crypto, Shamir, adaptive LSB determinism, seals, vault, shield, audio and PNG-chunk carriers, fuzzing of all untrusted parsers, CLI end-to-end, persistent history, and email safety
- Versioned, authenticated on-disk format with backward-compatible v1 decryption
- No deprecated Pillow APIs (Pillow 14 compatible through 2027+)

## Build a standalone executable

```bash
pip install pyinstaller
pyinstaller StegoXpress.spec
```

## License

Proprietary commercial software — Copyright (c) 2026 Nakum-hub. All rights reserved.

StegoXpress v2.0.0 and later are distributed under the [StegoXpress Proprietary Software License](LICENSE). Purchase of a license grants personal / internal business use; redistribution and resale are not permitted. For commercial, OEM, or source-code licensing, contact the author via [GitHub](https://github.com/Nakum-hub).

*(Versions released before 12 June 2026 remain available under the MIT License that applied to them at the time.)*

## Disclaimer

This tool is for lawful use: protecting your own data, research, and education. You are responsible for complying with the laws of your jurisdiction.
