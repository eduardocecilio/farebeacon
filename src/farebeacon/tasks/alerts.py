from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select, update

from farebeacon.config import get_settings
from farebeacon.domain.enums import AlertEventStatus
from farebeacon.domain.ports.notifications import NotificationDeliveryError, NotificationMessage
from farebeacon.infrastructure.db.models import AlertEvent
from farebeacon.infrastructure.db.session import database
from farebeacon.infrastructure.notifications import build_notifier
from farebeacon.tasks.celery_app import celery_app

LOGGER = logging.getLogger("farebeacon.alerts")


@celery_app.task(name="farebeacon.dispatch_alert_event")  # type: ignore[untyped-decorator]
def dispatch_alert_event(event_id: str) -> dict[str, str | int]:
    settings = get_settings()
    notifier = build_notifier(settings)
    if notifier is None:
        with database.session() as session:
            changed_id = session.scalar(
                update(AlertEvent)
                .where(
                    AlertEvent.id == event_id,
                    AlertEvent.status == AlertEventStatus.PENDING.value,
                )
                .values(
                    status=AlertEventStatus.SUPPRESSED.value,
                    suppression_reason="notification backend is disabled",
                )
                .returning(AlertEvent.id)
            )
            session.commit()
            changed = changed_id is not None
        return {
            "event_id": event_id,
            "status": AlertEventStatus.SUPPRESSED.value if changed else "unchanged",
        }

    now = datetime.now(UTC)
    with database.session() as session:
        event = session.get(AlertEvent, event_id)
        if event is None:
            return {"event_id": event_id, "status": "missing"}
        message_text = event.message
        if not message_text:
            if event.status == AlertEventStatus.PENDING.value:
                event.status = AlertEventStatus.FAILED.value
                event.error_message = "Alert event has no rendered message."
                session.commit()
            return {"event_id": event_id, "status": event.status}
        claimed_id = session.scalar(
            update(AlertEvent)
            .where(
                AlertEvent.id == event_id,
                AlertEvent.status == AlertEventStatus.PENDING.value,
            )
            .values(
                status=AlertEventStatus.SENDING.value,
                provider=notifier.name,
                attempt_count=AlertEvent.attempt_count + 1,
                last_attempt_at=now,
                error_message=None,
            )
            .returning(AlertEvent.id)
        )
        session.commit()
        if claimed_id is None:
            current_status = session.scalar(
                select(AlertEvent.status).where(AlertEvent.id == event_id)
            )
            return {"event_id": event_id, "status": current_status or "missing"}

    try:
        receipt = notifier.send(NotificationMessage(event_id=event_id, text=message_text))
    except NotificationDeliveryError as error:
        _mark_delivery_failed(event_id, str(error))
        return {"event_id": event_id, "status": AlertEventStatus.FAILED.value}
    except Exception:
        LOGGER.error(
            "notification delivery failed unexpectedly",
            extra={"alert_event_id": event_id, "provider": notifier.name},
        )
        _mark_delivery_failed(event_id, "Notification delivery failed unexpectedly.")
        return {"event_id": event_id, "status": AlertEventStatus.FAILED.value}

    with database.session() as session:
        event = session.get(AlertEvent, event_id)
        if event is not None and event.status == AlertEventStatus.SENDING.value:
            event.status = AlertEventStatus.SENT.value
            event.provider_message_id = receipt.provider_message_id
            event.sent_at = datetime.now(UTC)
            session.commit()
    return {
        "event_id": event_id,
        "status": AlertEventStatus.SENT.value,
        "attempt_count": 1,
    }


@celery_app.task(name="farebeacon.dispatch_pending_alerts")  # type: ignore[untyped-decorator]
def dispatch_pending_alerts() -> dict[str, int]:
    with database.session() as session:
        event_ids = list(
            session.scalars(
                select(AlertEvent.id)
                .where(AlertEvent.status == AlertEventStatus.PENDING.value)
                .order_by(AlertEvent.created_at)
                .limit(100)
            ).all()
        )
    return {"enqueued": queue_alert_events(event_ids)}


def queue_alert_events(event_ids: list[str]) -> int:
    enqueued = 0
    for event_id in event_ids:
        try:
            dispatch_alert_event.apply_async(args=[event_id], queue="notifications")
        except Exception:
            LOGGER.error(
                "alert event could not be queued",
                extra={"alert_event_id": event_id},
            )
        else:
            enqueued += 1
    return enqueued


def _mark_delivery_failed(event_id: str, message: str) -> None:
    with database.session() as session:
        event = session.get(AlertEvent, event_id)
        if event is not None and event.status == AlertEventStatus.SENDING.value:
            event.status = AlertEventStatus.FAILED.value
            event.error_message = message[:2000]
            session.commit()
