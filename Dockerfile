# ── StegoXpress — headless development / CI image ──────────────────────────
#
# This image runs tests and the CLI without a display (no GUI).
# The GUI requires a real desktop session (X11 / Wayland / Windows / macOS).
#
# Build:
#   docker build -t stegoxpress-dev .
#
# Run tests:
#   docker run --rm stegoxpress-dev
#
# Use interactively:
#   docker run --rm -it -v $(pwd):/workspace stegoxpress-dev bash
#
# Run a single CLI command:
#   docker run --rm -v $(pwd)/output:/out stegoxpress-dev \
#       python main.py encode --image assets/logo.png --text "hi" \
#       --password "pw" --output /out/stego.png

FROM python:3.12-slim AS base

# System libs required by Pillow (libjpeg, zlib, libpng) and numpy
RUN apt-get update && apt-get install -y --no-install-recommends \
        libjpeg62-turbo \
        zlib1g \
        libpng16-16 \
        libfreetype6 \
        liblcms2-2 \
        libwebp7 \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Install Python deps first (layer-cached when source changes but deps don't)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir argon2-cffi pytest pytest-cov

# Copy project source
COPY . .

# Smoke-test that all imports succeed (catches missing hidden deps early)
RUN python -c "
from core.lsb_engine import LSBEngine
from core.crypto_engine import CryptoEngine
from core.vault_engine import VaultEngine
from core.shamir_engine import ShamirEngine
from core.shield_engine import ShieldEngine
from core.audio_engine import AudioEngine
from core.png_chunk_engine import PngChunkEngine
from core.shield_engine import ShieldEngine
from transport.key_manager import KeyManager
from utils.config import Config
from utils.history import PersistentHistory
print('All imports OK')
print('Argon2id:', CryptoEngine.argon2_available())
"

# Default command: run the full test suite
CMD ["python", "-m", "pytest", "tests/", "-v", "--tb=short", \
     "--cov=core", "--cov=transport", "--cov=utils", \
     "--cov-report=term-missing"]
