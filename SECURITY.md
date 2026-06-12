# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 2.x     | ✅ Active  |
| 1.x     | ❌ No      |

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Email the maintainer with:
- A clear description of the vulnerability
- Steps to reproduce
- Potential impact assessment

You will receive a response within 72 hours. Critical issues will be
patched and released within 7 days of a confirmed report.

## Security Model

| Component | Implementation |
|---|---|
| Encryption | AES-256-GCM (authenticated — detects tampering at cipher layer) |
| Key derivation | PBKDF2-HMAC-SHA256, 480,000 iterations, 16-byte random salt |
| Steganography | 1-bit LSB per RGB channel with 4-byte length header |
| Vault | Dual-zone pixel split; each zone independently AES-256-GCM encrypted |
| Shield | Shamir's Secret Sharing over GF(257); AES-256-GCM per share |
| Seal | HMAC-SHA256 over payload bytes; detects any bit modification |
| Email transport | Only the stego image is sent; no key, salt, nonce, or ciphertext metadata in body |

## Known Limitations

1. **LSB is not covert against statistical steganalysis.** A chi-square or RS
   analysis on sequential LSB embeddings can detect that an image has been
   modified. Adaptive LSB mode reduces this significantly but does not
   eliminate it on low-entropy (solid-colour) images.

2. **JPEG output destroys LSB data.** Always save stego images as PNG.
   The app enforces this, but users who manually re-save as JPEG will lose data.

3. **Password strength is the primary security factor.** AES-256-GCM with a
   weak password is still weak. Use 16+ characters with mixed character classes.

4. **Vault deniability depends on password secrecy.** If both passwords are
   extracted, both messages are revealed. The vault provides plausible deniability
   only when the decoy password is all the attacker knows.
