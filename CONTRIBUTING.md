# Contributing to StegoXpress

Thank you for looking at the code. This document covers everything you need to get from zero to a passing test suite and a ready-to-merge pull request.

## Table of contents

1. [Ground rules](#ground-rules)
2. [Dev environment setup](#dev-environment-setup)
3. [Project structure](#project-structure)
4. [Running tests](#running-tests)
5. [Writing tests](#writing-tests)
6. [Code style](#code-style)
7. [Security contributions](#security-contributions)
8. [Pull request checklist](#pull-request-checklist)

---

## Ground rules

- **Security first.** Any change that touches `core/crypto_engine.py`, `core/lsb_engine.py`, `core/vault_engine.py`, `core/shamir_engine.py`, or `transport/` requires a security rationale in the PR description.
- **No new dependencies without justification.** Every added package is an attack surface. If you add one, explain why it can't be done with stdlib or an existing dep.
- **Tests are not optional.** New features need new tests. Bug fixes need a regression test that fails before the fix and passes after.
- **No plaintext credentials, keys, or real personal data in commits.** The test suite uses randomly generated images and fixed test passwords — keep it that way.

---

## Dev environment setup

### With Docker (recommended — no display required)

```bash
git clone https://github.com/Nakum-hub/StegoXpress.git
cd StegoXpress
docker compose run --rm test          # run full test suite
docker compose run --rm dev           # interactive shell
```

### Without Docker

Python 3.10 or later required.

```bash
git clone https://github.com/Nakum-hub/StegoXpress.git
cd StegoXpress
python -m venv .venv
source .venv/bin/activate             # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e ".[dev]"               # installs pytest, ruff, mypy, pip-audit
```

Verify everything works:
```bash
python -m pytest tests/ -q            # all green?
python main.py version                # prints StegoXpress 2.x.x?
python main.py info --image assets/logo.png
```

---

## Project structure

```
StegoXpress/
├── main.py               Entry point: CLI dispatcher + subcommand handlers
├── core/
│   ├── crypto_engine.py  AES-256-GCM, Argon2id/PBKDF2 KDF, bundle versioning
│   ├── lsb_engine.py     LSB embed/extract, adaptive mode, entropy heatmap, steganalysis
│   ├── vault_engine.py   Dual-password hidden volumes (NumPy pixel I/O)
│   ├── shamir_engine.py  Shamir secret sharing over GF(2^8)
│   ├── shield_engine.py  N-of-K image sharing (wraps Shamir + LSBEngine)
│   ├── audio_engine.py   WAV audio LSB carrier
│   ├── png_chunk_engine.py  Private PNG metadata chunk carrier
│   ├── file_packer.py    Payload serialization: text, file, sealed, self-destruct
│   └── shield_engine.py  Multi-image secret sharing
├── gui/
│   ├── app.py            CustomTkinter root window and tab setup
│   ├── encode_tab.py     GUI encode flow
│   ├── decode_tab.py     GUI decode flow (includes clipboard copy)
│   ├── send_tab.py       Email sender tab
│   ├── vault_tab.py      GUI dual-password vault
│   ├── shield_tab.py     GUI N-of-K sharing
│   ├── history_tab.py    Operation history (reads/writes PersistentHistory)
│   ├── widgets.py        Reusable CTk components, colours, fonts
│   └── dnd.py            Drag-and-drop helpers
├── transport/
│   ├── email_sender.py   SMTP/TLS email with stego image attachment
│   └── key_manager.py    One-time token generation (NOT the password itself)
├── utils/
│   ├── config.py         Persistent user config (SMTP host, theme, etc.)
│   ├── history.py        PersistentHistory — JSON operation log in ~/.stegoxpress/
│   └── logger.py         Rotating file logger
├── tests/
│   ├── conftest.py       (Intentionally minimal — see note below)
│   ├── test_upgrade.py   Core crypto and Shamir tests
│   ├── test_carriers_v2.py  All carrier roundtrip tests
│   └── test_production.py   CLI, history, vault, email, steganalysis tests
├── assets/               Logo, banner, icon
├── docs/                 Upgrade notes and architecture notes
├── Dockerfile            Headless CI/dev image
├── docker-compose.yml    Service definitions: test, dev, cli
├── StegoXpress.spec      PyInstaller build spec
├── pyproject.toml        Build config, deps, tool config
├── requirements.txt      Pinned runtime deps (incl. argon2-cffi)
├── SECURITY.md           Threat model and responsible disclosure
└── CHANGELOG.md          Version history
```

**conftest.py note:** it is intentionally almost empty. Do NOT add `subprocess.check_call(["pip", "install", ...])` to it — that was an anti-pattern removed in v2.1. Install deps with `pip install -r requirements.txt` before running tests.

---

## Running tests

```bash
# All tests
python -m pytest tests/ -v

# With coverage
python -m pytest tests/ --cov=core --cov=transport --cov=utils --cov-report=term-missing

# One file
python -m pytest tests/test_production.py -v

# One test
python -m pytest tests/test_production.py::test_cli_seal_roundtrip -v

# Via Docker
docker compose run --rm test
```

---

## Writing tests

All tests live in `tests/`. Use `tests/test_production.py` as the template.

Key conventions:

```python
import numpy as np
from PIL import Image

def _rand_image(w=128, h=128, seed=42):
    """Always use seeded NumPy for reproducible carrier images."""
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)
    return Image.fromarray(arr, "RGB")

def _run_cli(*args):
    import main as m
    return m.run_cli(list(args))
```

Rules:
- Use `tmp_path` (pytest fixture) for all file output — never hardcode `/tmp/`.
- Use `monkeypatch` to redirect `PersistentHistory` storage so tests don't write to your home directory.
- Test exit codes, not just zero-vs-non-zero. `EXIT_WRONG_PASSWORD = 1`, `EXIT_CAPACITY = 2`, `EXIT_FILE_NOT_FOUND = 3`.
- Any new encryption format change needs a decrypt-legacy test: encode with the old path, decrypt with the new code.

---

## Code style

StegoXpress uses `ruff` for linting and `mypy` for type checking.

```bash
ruff check core/ transport/ utils/ main.py tests/   # lint
mypy core/ transport/ utils/ main.py                # type check
pip-audit -r requirements.txt                       # dependency audit
```

All three must pass before opening a PR. CI enforces this.

Style notes:
- Line length: 100 chars (`ruff` enforces).
- Type hints on all public functions (return types required).
- Docstrings on all classes and non-trivial functions. One-liners are fine for obvious helpers.
- No `print()` in library code (`core/`, `transport/`, `utils/`) — use `StegoLogger.get()`.

---

## Security contributions

If you find a security vulnerability, **do not open a public issue**. Email the author via GitHub (see profile) or follow the process in [SECURITY.md](SECURITY.md).

For non-vulnerability security improvements (hardening, KDF tuning, audit findings):
- Open a PR with `security:` prefix in the title.
- Include a threat model note: what attack does this defend against, what is the realistic attacker capability, what does it not defend against?
- The existing `SECURITY.md` honest-threat-model section is the bar to match.

---

## Pull request checklist

Before submitting:

- [ ] `python -m pytest tests/ -q` — all tests pass
- [ ] `ruff check core/ transport/ utils/ main.py tests/` — no lint errors
- [ ] `mypy core/ transport/ utils/ main.py` — no type errors
- [ ] New feature → new test(s) added
- [ ] Bug fix → regression test that catches the bug added
- [ ] `CHANGELOG.md` updated under `[Unreleased]` section
- [ ] Sensitive data (passwords, real keys, personal info) not present in commits
- [ ] PR description explains the *why*, not just the *what*
