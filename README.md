# StegoXpress ◈

![CI](https://github.com/Nakum-hub/StegoXpress/actions/workflows/tests.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Tests](https://img.shields.io/badge/tests-77%20passed-brightgreen)

**Hide encrypted secrets inside images, audio, and PNG metadata.**
The only Python steganography tool with dual-password hidden volumes,
multi-carrier support, N-of-K secret sharing, and real-time steganalysis scoring.

---

## What Makes This Different

| Feature | StegoXpress ◈ | Other tools |
|---|:---:|:---:|
| Dual-password hidden volumes (StegoVault) | ✅ | ❌ |
| N-of-K Shamir secret sharing (StegoShield) | ✅ | ❌ |
| Audio (WAV) carrier | ✅ | Rarely |
| PNG metadata carrier (zero pixel change) | ✅ | ❌ |
| HMAC tamper-proof seal | ✅ | ❌ |
| Self-destruct after decode | ✅ | ❌ |
| Live RS steganalysis score | ✅ | ❌ |
| Entropy heatmap | ✅ | ❌ |
| Adaptive LSB (high-entropy pixels only) | ✅ | ❌ |
| CLI + GUI | ✅ | Rarely |
| Password-based (no raw key transmitted) | ✅ | Rarely |

---

## Features

### 🔒 Core
- **AES-256-GCM** encryption with PBKDF2-HMAC-SHA256 (480,000 iterations)
- **LSB steganography** — length-prefixed, handles text and any file type
- **Adaptive LSB** — embeds only in high-entropy regions to reduce detectability

### 🔐 StegoVault
Embed a **decoy** AND a **real** message in one image.
- Password A → decoy message (what you show under pressure)
- Password B → real message (the actual secret)
- No structural evidence that a second message exists

### 🛡 StegoShield
Split one secret across **N images**. Any **K** images reconstruct it.
- Uses Shamir's Secret Sharing over GF(257)
- Ideal for teams — no single person can decode alone

### 🎵 MultiCarrier
- **Image LSB** — 1 bit per RGB channel, PNG output
- **Audio WAV** — LSB of 16-bit PCM samples, WAV output
- **PNG Metadata** — private "stXp" chunk; zero pixel modification

### 🔏 StegoSeal & Self-Destruct
- **Seal** — HMAC-SHA256 integrity check; decoding fails if image modified
- **Self-Destruct** — LSB layer zeroed after first successful decode

### 📊 Analysis Tools
- **Entropy Heatmap** — visual overlay of safe pixel zones (blue→red gradient)
- **Steganalysis Score** — RS-analysis detectability: Low / Medium / High Risk

---

## Install

```bash
pip install -r requirements.txt
```

## Run GUI

```bash
python main.py
```

## CLI

```bash
# Hide text
python main.py encode --image cover.png --message "secret text" --password p --output out.png

# Hide a file
python main.py encode --image cover.png --file secret.pdf --password p --output out.png

# Decode
python main.py decode --image out.png --password p
```

## Run Tests

```bash
python -m pytest tests/ -v
```

## Build EXE (Windows)

```bash
pyinstaller StegoXpress.spec
```

---

## Project Structure

```
core/
  lsb_engine.py        Standard + adaptive LSB, heatmap, steganalysis
  crypto_engine.py     AES-256-GCM + PBKDF2 key derivation
  file_packer.py       Binary payload format (text/file/vault/sealed/self-destruct)
  vault_engine.py      Dual-password hidden volumes
  audio_engine.py      WAV LSB steganography
  png_chunk_engine.py  PNG ancillary chunk steganography
  shamir_engine.py     Shamir's Secret Sharing over GF(257)
  shield_engine.py     N-of-K multi-image secret sharing
gui/
  app.py               Main window + 6 tabs
  encode_tab.py        Encode UI (carrier, heatmap, seal, adaptive toggles)
  decode_tab.py        Decode UI (carrier, seal verification, self-destruct)
  vault_tab.py         StegoVault UI
  shield_tab.py        StegoShield UI
  send_tab.py          Secure email (image only, no key in body)
  history_tab.py       Session history
  widgets.py           Design system + reusable widgets
transport/
  email_sender.py      Multi-provider SMTP
  key_manager.py       Password strength + QR hint
utils/
  config.py            Persistent settings
  logger.py            Rotating file log
tests/                 77 tests across all modules
main.py                CLI + GUI entry point
```

## Security

See [SECURITY.md](SECURITY.md) for the full security model, known limitations,
and vulnerability reporting process.

## License

MIT — see [LICENSE](LICENSE)
