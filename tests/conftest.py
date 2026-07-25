"""Shared pytest configuration."""

import os

# Qt widget tests (pytest-qt) must not require a real display in CI/headless
# environments. Setting this before any PySide6 import is safe and has no
# effect on the rest of the test suite, which doesn't use Qt at all.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
