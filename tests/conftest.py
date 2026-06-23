"""
Pytest configuration for StegoXpress.

All runtime dependencies must be installed before running tests.
Use:  pip install -r requirements.txt
      pip install -e ".[dev]"

The previous conftest.py used subprocess.check_call to self-install numpy at
test-collection time. That pattern is an anti-pattern: it mutates the test
environment silently, is a security risk in CI, and hides missing dependencies
instead of surfacing them. It has been removed. If numpy is not present, pytest
will fail at import time with a clear ImportError — which is the correct signal.
"""
