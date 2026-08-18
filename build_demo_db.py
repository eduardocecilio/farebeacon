"""Build the demo database that ships inside the deployment bundle.

Vercel runs this as the build command, after dependencies are installed and before the deployment is
packaged. It creates a SQLite file with deterministic MockSource data, so the public demo needs no
managed database, no account, and no credential.

The schema comes from the SQLAlchemy models, which is also how the test suite builds its database.
Alembic stays the path for PostgreSQL deployments: migration 0002 adds foreign-key columns, and
SQLite cannot ALTER constraints.

After building, it boots the deployment entrypoint and exercises the routes the demo depends on. A
misconfigured environment then fails the build with a real traceback, instead of deploying a
function that answers every request with an opaque platform error.

The file is disposable by design: every deployment rebuilds it. A deployment that needs durable
state sets `FAREBEACON_DATABASE_URL` instead, and this database is then ignored at runtime. See
docs/vercel-demo.md.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATABASE_PATH = ROOT / "demo.db"
VERIFY_FLAG = "--verify"
# Captured before this script sets anything: what the platform actually hands the deployment.
PLATFORM_ENVIRONMENT = dict(os.environ)


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

    from farebeacon.infrastructure.db.models import Base
    from farebeacon.infrastructure.db.session import database
    from farebeacon.scripts.seed_demo import seed

    Base.metadata.create_all(database.engine)

    with database.session() as session:
        monitor_ids = seed(session)

    print(f"demo database built at {DATABASE_PATH} with {len(monitor_ids)} monitors")

    # A clean interpreter is the only way to exercise what the deployment actually does: configure
    # itself around the bundled database. This process already bound its engine to the build path
    # and set variables to build it.
    neutral = {
        key: value
        for key, value in PLATFORM_ENVIRONMENT.items()
        if not key.startswith("FAREBEACON_")
    }
    print("verifying the zero-configuration deployment")
    _boot(neutral)

    # The deployment does not run with a neutral environment: it runs with whatever this project
    # configures. A variable that cannot produce a working application must fail the build here,
    # not answer every request with a platform error afterwards.
    configured = {
        key: value
        for key, value in PLATFORM_ENVIRONMENT.items()
        if key != "FAREBEACON_DATABASE_URL"
    }
    if any(key.startswith("FAREBEACON_") for key in configured):
        declared = sorted(key for key in configured if key.startswith("FAREBEACON_"))
        print(f"verifying the configured environment: {', '.join(declared)}")
        _boot(configured)


def _boot(environment: dict[str, str]) -> None:
    subprocess.run([sys.executable, __file__, VERIFY_FLAG], check=True, env=environment)


def verify() -> None:
    """Boot the deployment entrypoint the way the platform boots it."""
    source_root = ROOT / "src"
    if source_root.is_dir() and str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from fastapi.testclient import TestClient

    import app as entrypoint

    with TestClient(entrypoint.app) as client:
        health = client.get("/health")
        assert health.status_code == 200, health.text

        ready = client.get("/ready")
        assert ready.status_code == 200, ready.text
        assert "redis" not in ready.json()["data"]["checks"], ready.text

        monitors = client.get("/api/v1/monitors")
        assert monitors.status_code == 200, monitors.text
        total = monitors.json()["data"]["total"]
        assert total > 0, monitors.text

        rejected = client.post(
            "/api/v1/monitors",
            headers={"Idempotency-Key": "deployment-boot-check"},
            json={},
        )
        assert rejected.status_code == 401, rejected.text

    print(
        f"deployment entrypoint served {total} seeded monitors with no configuration "
        "and refused an anonymous write"
    )


if __name__ == "__main__":
    if VERIFY_FLAG in sys.argv[1:]:
        verify()
    else:
        main()
