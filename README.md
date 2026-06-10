# StegoXpress

StegoXpress is a Python steganography application for hiding encrypted text or files inside images with LSB encoding. It uses a password-based workflow, so no raw encryption key is emailed or stored in the image transport channel.

## Features

- Hide text or arbitrary files inside PNG-safe stego images.
- Recover text or files with the agreed password.
- AES-256-GCM encryption with PBKDF2-HMAC-SHA256 password derivation.
- 4-byte length-prefixed LSB payload encoding.
- CustomTkinter desktop GUI with Encode, Decode, and Send workflows.
- SMTP transport for Gmail, Outlook, Yahoo, or custom providers.
- Email sends only the stego image. Passwords must be shared out-of-band.

## Project Structure

```text
core/
  lsb_engine.py       # Length-prefixed LSB image encoder/decoder
  crypto_engine.py    # PBKDF2 + AES-GCM encryption
  file_packer.py      # Text/file payload packing format
gui/
  app.py              # Main CustomTkinter app shell
  encode_tab.py       # Encode and hide workflow
  decode_tab.py       # Decode and extract workflow
  send_tab.py         # Secure email transport workflow
  widgets.py          # Shared design-system widgets
transport/
  email_sender.py     # SMTP provider transport
  key_manager.py      # Password hint QR and strength helper
tests/
  test_roundtrip.py
  test_transport.py
main.py               # GUI entry point
```

## Install

```powershell
python -m pip install -r requirements.txt
```

## Run

```powershell
python main.py
```

## Test

```powershell
python -m pytest -q
```

Expected result:

```text
17 passed
```

## Secure Email Workflow

1. Encode text or a file into a cover image using a strong password.
2. Send only the generated stego PNG through the Send tab.
3. Share the password with the recipient through a separate channel.
4. The recipient opens the stego image in the Decode tab and enters the agreed password.

The email body never includes the password, raw key, salt, nonce, or ciphertext metadata beyond the attached stego image.

## Notes

- Use PNG output for stego images. Lossy formats such as JPEG can destroy hidden LSB data after encoding.
- Gmail, Yahoo, and Outlook usually require app passwords for SMTP login.
- Build artifacts in `build/` and `dist/` are ignored and should be regenerated locally when needed.
