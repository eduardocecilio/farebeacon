"""Vercel Function entrypoint.

The application lives in `src/farebeacon`. Vercel resolves an entrypoint as a path from the project
root, so this module puts `src` on the import path before exporting the ASGI application. Running
the Compose stack, the tests, or `uvicorn farebeacon.api.main:app` does not go through this file.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from farebeacon.api.main import app  # noqa: E402

__all__ = ["app"]
