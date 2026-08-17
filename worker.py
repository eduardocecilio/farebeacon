"""Vercel Queues subscriber entrypoint for the Celery application.

Vercel compiles this entrypoint into a private, queue-triggered Vercel Function instead of a
long-lived `celery worker` process. Importing the Celery application registers every task module,
which is what the build introspects to discover the declared queues.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from farebeacon.tasks.celery_app import celery_app as app  # noqa: E402

__all__ = ["app"]
