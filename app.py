"""Vercel Function entrypoint.

The application lives in `src/farebeacon`. Vercel resolves an entrypoint as a path from the project
root, so this module puts `src` on the import path before exporting the ASGI application. Running
the Compose stack, the tests, or `uvicorn farebeacon.api.main:app` does not go through this file.

It also prepares the two paths a serverless function cannot use as they are: the bundled demo
database, which is read-only inside the deployment, and the artifact root, which must live under the
only writable directory. Both steps are skipped when the deployment brings its own database.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUNDLED_DEMO_DATABASE = ROOT / "demo.db"

_SRC = ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

_TEMPORARY_ROOT = Path(tempfile.gettempdir())
os.environ.setdefault("FAREBEACON_ARTIFACTS_ROOT", str(_TEMPORARY_ROOT / "farebeacon-artifacts"))

if not os.environ.get("FAREBEACON_DATABASE_URL") and BUNDLED_DEMO_DATABASE.is_file():
    _RUNTIME_DATABASE = _TEMPORARY_ROOT / "farebeacon-demo.db"
    if not _RUNTIME_DATABASE.is_file():
        shutil.copy2(BUNDLED_DEMO_DATABASE, _RUNTIME_DATABASE)
    os.environ["FAREBEACON_DATABASE_URL"] = f"sqlite+pysqlite:///{_RUNTIME_DATABASE}"
    os.environ.setdefault("FAREBEACON_CELERY_TASK_ALWAYS_EAGER", "true")

from farebeacon.api.main import app  # noqa: E402

__all__ = ["app"]
