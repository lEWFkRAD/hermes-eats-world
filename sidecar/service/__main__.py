"""Hermes Eats World — Sidecar service entry point.

Usage:
    python -m sidecar.service --target "File Explorer"
    python -m sidecar.service --process notepad.exe --depth 5
    python -m sidecar.service --list
"""

import sys

from .cli import main

sys.exit(main())
