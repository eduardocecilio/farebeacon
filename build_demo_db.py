"""Build the demo database that ships inside the deployment bundle.

Vercel runs this as the build command, after dependencies are installed and before the deployment is
packaged. It creates a SQLite file with the real Alembic schema and deterministic MockSource data, so
the public demo needs no managed database, no account, and no credential.

The file is disposable by design: every deployment rebuilds it. A deployment that needs durable
state sets `FAREBEACON_DATABASE_URL` instead, and this database is then ignored at runtime. See
docs/vercel-demo.md.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATABASE_PATH = ROOT / "demo.db"


def main() -> None:
    DATABASE_PATH.unlink(missing_ok=True)
    os.environ["FAREBEACON_DATABASE_URL"] = f"sqlite+pysqlite:///{DATABASE_PATH}"
    os.environ["FAREBEACON_CELERY_TASK_ALWAYS_EAGER"] = "true"
    os.environ["FAREBEACON_NOTIFICATION_BACKEND"] = "disabled"
    os.environ.setdefault("FAREBEACON_ENV", "demo")
    os.environ.setdefault("FAREBEACON_ARTIFACTS_ROOT", "/tmp/farebeacon-artifacts")

    source_root = ROOT / "src"
    if source_root.is_dir() and str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))

    from alembic import command
    from alembic.config import Config

    alembic_config = Config(str(ROOT / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(ROOT / "migrations"))
    command.upgrade(alembic_config, "head")

    from farebeacon.infrastructure.db.session import database
    from farebeacon.scripts.seed_demo import seed

    with database.session() as session:
        monitor_ids = seed(session)

    print(f"demo database built at {DATABASE_PATH} with {len(monitor_ids)} monitors")


if __name__ == "__main__":
    main()
