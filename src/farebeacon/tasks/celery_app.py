from __future__ import annotations

from celery import Celery  # type: ignore[import-untyped]

from farebeacon.config import get_settings

settings = get_settings()

celery_app = Celery(
    "farebeacon",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "farebeacon.tasks.orchestration",
        "farebeacon.tasks.sources",
        "farebeacon.tasks.normalization",
        "farebeacon.tasks.alerts",
        "farebeacon.tasks.scheduler",
    ],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=True,
    task_store_eager_result=False,
    task_routes={
        "farebeacon.orchestrate_run": {"queue": "orchestration"},
        "farebeacon.execute_source_run": {"queue": "source.mock"},
        "farebeacon.normalize_source_results": {"queue": "normalize"},
        "farebeacon.dispatch_alert_event": {"queue": "notifications"},
        "farebeacon.dispatch_pending_alerts": {"queue": "maintenance"},
        "farebeacon.enqueue_due_monitors": {"queue": "maintenance"},
    },
    beat_schedule={
        "enqueue-due-monitors": {
            "task": "farebeacon.enqueue_due_monitors",
            "schedule": 60.0,
        },
        "dispatch-pending-alerts": {
            "task": "farebeacon.dispatch_pending_alerts",
            "schedule": 60.0,
        },
    },
)
