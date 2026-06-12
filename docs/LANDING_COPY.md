# StegoXpress — Landing Page & Sales Copy

Ready-to-paste copy for a product page (Gumroad / Lemon Squeezy / personal site).

---

## Hero

**Headline:** Your secrets, hidden in plain sight.

**Subheadline:** StegoXpress locks your message with AES-256 encryption, then hides it inside an ordinary photo, song, or file. To everyone else, it's just a picture.

**CTA button:** Buy StegoXpress Pro

---

## Three-point pitch

1. **Encrypt first, hide second.** Even if someone suspects the image, the payload is AES-256-GCM encrypted with a key derived from your password through 600,000 PBKDF2 rounds.
2. **A decoy for coercion.** StegoVault holds two messages: hand over the decoy password, keep the real one. (Best-effort deniability — we tell you exactly how far it goes.)
3. **No single point of failure.** StegoShield splits a secret across 5 images; any 3 reconstruct it. Lose two, you're still safe. An attacker with two learns nothing.

---

## Feature grid

| | |
|---|---|
| **4 carriers** — image LSB, adaptive LSB, WAV audio, PNG metadata | **Tamper seal** — know instantly if the file was altered |
| **Detectability score** — see how 'visible' your secret is before sending | **Burn-after-read** — erase the local copy after first decode |
| **Dark-mode GUI + scriptable CLI** — humans and pipelines welcome | **Offline & telemetry-free** — the only network call is the email *you* trigger |

---

## Trust section

- Professionally audited codebase: a full security review fixed every critical finding before release (the audit and fixes are documented in the changelog)
- CI-tested on Python 3.10–3.12 with linting, type-checking, coverage, and dependency CVE audits
- An honest threat model: we document what steganography **cannot** do, because security products that overpromise get people hurt
- No telemetry, no accounts, no cloud — everything runs on your machine

---

## Pricing (suggested)

| Tier | Price | Includes |
|---|---|---|
| Personal | $19 one-time | Compiled desktop app (Win/macOS/Linux), personal-use license |
| Pro | $39 one-time | Personal + full source code, CLI for scripting, priority email support |
| Business | $99/yr | Pro + commercial-use license, invisible watermarking toolkit for leak-tracing |

---

## FAQ snippets

**Is this legal?** Encryption and steganography are legal in most jurisdictions for protecting your own data. You are responsible for lawful use.

**Can it be detected?** Small payloads in adaptive mode are very hard to spot, but no steganography is mathematically invisible. The built-in detectability score tells you your risk before you send.

**What if I lose my password?** It's gone. There is no backdoor — that's the point.

**Can I redistribute it?** No — StegoXpress is proprietary commercial software. Your license covers your own use; resale and redistribution require a separate agreement.

---

## One-paragraph pitch (for emails / marketplaces)

> StegoXpress hides AES-256-GCM-encrypted secrets inside ordinary images, audio, and PNG metadata — with dual-password decoy vaults, N-of-K secret sharing, and built-in steganalysis scoring. Security-audited, CI-tested, polished desktop app + scriptable CLI, and a B2B invisible-watermarking edition for tracing leaked media.
