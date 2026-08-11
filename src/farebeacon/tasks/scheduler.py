from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from farebeacon.api.errors import AppError
from farebeacon.application.runs import create_search_run
from farebeacon.domain.enums import RunTrigger
from farebeacon.infrastructure.db.models import Monitor
from farebeacon.infrastructure.db.session import database
from farebeacon.tasks.celery_app import celery_app
from farebeacon.tasks.orchestration import orchestrate_run


@celery_app.task(name="farebeacon.enqueue_due_monitors")  # type: ignore[untyped-decorator]
def enqueue_due_monitors() -> dict[str, int]:
    now = datetime.now(UTC)
    enqueued = 0
    with database.session() as session:
        monitor_ids = list(
            session.scalars(
                select(Monitor.id).where(
                    Monitor.is_active.is_(True),
                    Monitor.next_run_at.is_not(None),
                    Monitor.next_run_at <= now,
                )
            ).all()
        )
    for monitor_id in monitor_ids:
        with database.session() as session:
            monitor = session.get(Monitor, monitor_id)
            if monitor is None or monitor.next_run_at is None:
                continue
            slot = monitor.next_run_at.isoformat()
            try:
                run, created = create_search_run(
                    session,
                    monitor_id=monitor_id,
                    idempotency_key=f"scheduled:{monitor_id}:{slot}",
                    trigger=RunTrigger.SCHEDULED,
                )
            except AppError as error:
                logging.getLogger("farebeacon.scheduler").warning(
                    "scheduled monitor was not enqueued",
                    extra={"monitor_id": monitor_id, "error_code": error.code},
                )
                continue
            monitor = session.get(Monitor, monitor_id)
            if monitor is not None:
                monitor.next_run_at = now + timedelta(minutes=monitor.check_interval_minutes)
                session.commit()
            if created:
                orchestrate_run.apply_async(args=[run.id], queue="orchestration")
                enqueued += 1
    return {"enqueued": enqueued}
