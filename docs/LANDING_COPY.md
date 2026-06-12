# StegoXpress — Landing Page & Sales Copy

Ready-to-paste copy for a product page (Gumroad / Lemon Squeezy / personal site).

---

## Hero

**Headline:** Your secrets, hidden in plain sight.

**Subheadline:** StegoXpress locks your message with AES-256 encryption, then hides it inside an ordinary photo, song, or file. To everyone else, it's just a picture.

**CTA button:** Download StegoXpress Pro

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

- Open-source core (MIT) — audit every line on GitHub
- CI-tested on Python 3.10–3.12 with linting, type-checking, coverage, and dependency CVE audits
- An honest threat model: we document what steganography **cannot** do, because security products that overpromise get people hurt

---

## Pricing (suggested)

| Tier | Price | Includes |
|---|---|---|
| Community | Free | Full open-source app, GitHub support |
| Pro | $29 one-time | Signed binaries (Win/macOS/Linux), batch mode, priority email support |
| Business | $99/yr | Pro + invisible watermarking toolkit for leak-tracing, license for commercial use |

---

## FAQ snippets

**Is this legal?** Encryption and steganography are legal in most jurisdictions for protecting your own data. You are responsible for lawful use.

**Can it be detected?** Small payloads in adaptive mode are very hard to spot, but no steganography is mathematically invisible. The built-in detectability score tells you your risk before you send.

**What if I lose my password?** It's gone. There is no backdoor — that's the point.

---

## One-paragraph pitch (for emails / marketplaces)

> StegoXpress hides AES-256-GCM-encrypted secrets inside ordinary images, audio, and PNG metadata — with dual-password decoy vaults, N-of-K secret sharing, and built-in steganalysis scoring. Open-source core, polished desktop app, and a B2B invisible-watermarking edition for tracing leaked media.
