"""Windows' default console codepage (cp1252) can't encode the arrows and
accented characters every CLI in this project prints — a fresh `pip
install` + the exact Quickstart command crashed with `UnicodeEncodeError`
on a clean Windows machine (found during the pre-publish clean-room test,
see CHANGELOG.md). Every CLI entry point calls `ensure_utf8_stdio()` first
so this works out of the box, without requiring `PYTHONIOENCODING=utf-8`
to be set by hand.
"""

from __future__ import annotations

import sys


def ensure_utf8_stdio() -> None:
    """Reconfigure stdout/stderr to UTF-8. A no-op on platforms where the
    console is already UTF-8 (Linux, macOS, modern Windows Terminal)."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
