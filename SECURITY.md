# Security Policy & Threat Model

StegoXpress hides encrypted data inside images. This document states honestly
what it protects against and what it does **not**. Read it before relying on the
tool for anything sensitive.

## Reporting a vulnerability

Please open a private security advisory on GitHub (Security → Advisories →
“Report a vulnerability”) or email the maintainer. Do not file public issues for
undisclosed vulnerabilities. We aim to acknowledge within 72 hours.

## Cryptography

- **Cipher:** AES-256-GCM (authenticated encryption). Tampering with the
  ciphertext, header, salt, or nonce causes decryption to fail rather than
  return corrupted plaintext.
- **Key derivation:** PBKDF2-HMAC-SHA256, 600,000 iterations, 16-byte random
  salt per message. This is tuned for 2024-era guidance. If you enable the
  optional `argon2-cffi` dependency, prefer Argon2id for new deployments.
- **Bundle format (v2):** `magic(4) | version(1) | salt(16) | nonce(12) |
  ciphertext+tag`. The header is bound into GCM as additional authenticated
  data (AAD). Legacy v1 bundles (no version byte, 480k iterations) still decrypt
  for backward compatibility.
- **Seals:** Tamper-proof seals use HMAC-SHA256 with a key derived via salted
  PBKDF2 (600k). The salt is stored alongside the MAC.

## What StegoXpress protects against

- A casual observer who sees the carrier image and does not suspect hidden data.
- Recovery of the secret without the password, even if hidden data is suspected
  (the payload is AES-256-GCM encrypted).
- Silent modification of the hidden payload (authenticated encryption + seals
  detect tampering).

## What it does NOT protect against (honest limitations)

- **Statistical steganalysis.** LSB embedding is detectable by tools such as
  RS analysis, chi-square, and StegExpose, especially as payload size grows.
  Adaptive mode reduces but does not eliminate this. Treat “undetectability” as
  a goal, not a guarantee.
- **Hidden-volume deniability is statistical, not absolute.** The vault feature
  splits the image into a decoy zone and a real zone. A forensic analyst who
  measures LSB randomness across the *entire* image may notice that the decoy
  only accounts for part of it. Do not rely on the vault against a determined,
  well-resourced adversary.
- **Self-destruct is best-effort, not a guarantee.** “Self-destruct” erases the
  LSB plane of the working copy in memory/output. It cannot guarantee deletion
  of copies the recipient already saved, backups, OS-level temp files, or data
  on journaled/SSD storage.
- **Lossy re-encoding destroys payloads.** Always use lossless carriers (PNG).
  Saving as JPEG, screenshotting, or social-media re-compression will destroy
  the hidden data. This is expected behavior, not a bug.
- **Endpoint compromise.** If the machine running StegoXpress is compromised
  (keylogger, memory scraper), no steganography tool can help.

## Operational guidance

- Use strong, unique passwords; the KDF slows brute force but cannot rescue a
  weak password.
- Exchange coordination tokens (`KeyManager.generate_one_time_token`) over a
  channel separate from the carrier image. Never QR-encode or transmit the
  password itself.
- Keep payloads small relative to image capacity to minimize detectability.

## Supported versions

| Version | Supported |
|---------|-----------|
| 2.x     | ✅        |
| 1.x     | ⚠️ decrypt-only compatibility |
