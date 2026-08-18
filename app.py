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

_SEED_ON_BOOT = False
if not os.environ.get("FAREBEACON_DATABASE_URL"):
    _RUNTIME_DATABASE = _TEMPORARY_ROOT / "farebeacon-demo.db"
    if not _RUNTIME_DATABASE.is_file() and BUNDLED_DEMO_DATABASE.is_file():
        # copyfile, not copy2: the bundled file may be read-only, and SQLite must be able to write
        # to the copy. Preserving the source mode would produce a database nobody can open.
        shutil.copyfile(BUNDLED_DEMO_DATABASE, _RUNTIME_DATABASE)
        _RUNTIME_DATABASE.chmod(0o600)
    _SEED_ON_BOOT = not _RUNTIME_DATABASE.is_file()
    os.environ["FAREBEACON_DATABASE_URL"] = f"sqlite+pysqlite:///{_RUNTIME_DATABASE}"
    # Forced, not defaulted: a per-instance database cannot be shared with a worker, and a leftover
    # variable from a Compose `.env` must not point this deployment at a broker that does not exist.
    os.environ["FAREBEACON_CELERY_TASK_ALWAYS_EAGER"] = "true"
    # Running on a disposable, seeded database is what makes this deployment a demo, so it carries
    # the demo posture by itself: public reads, refused writes, no notifications. Every value stays
    # overridable, and a deployment that configures its own database gets none of this.
    os.environ.setdefault("FAREBEACON_DEMO_READ_ONLY", "true")
    os.environ.setdefault("FAREBEACON_NOTIFICATION_BACKEND", "disabled")
    os.environ.setdefault("FAREBEACON_ENV", "demo")
    print(
        "farebeacon: ephemeral demo database in use; reads are public and writes are refused",
        file=sys.stderr,
    )

if _SEED_ON_BOOT:
    # The bundled database did not reach the function. Build the demo data here instead of serving
    # every request from a database file that cannot be created on a read-only filesystem.
    from farebeacon.infrastructure.db.models import Base  # noqa: E402
    from farebeacon.infrastructure.db.session import database  # noqa: E402
    from farebeacon.scripts.seed_demo import seed  # noqa: E402

    Base.metadata.create_all(database.engine)
    with database.session() as _session:
        seed(_session)

from farebeacon.api.main import app  # noqa: E402

__all__ = ["app"]
