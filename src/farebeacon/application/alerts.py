from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from farebeacon.api.errors import AppError
from farebeacon.api.schemas import AlertEventRead
from farebeacon.domain.enums import AlertEventStatus, RunStatus
from farebeacon.domain.money import minor_to_decimal
from farebeacon.infrastructure.db.models import (
    AlertEvent,
    AlertRule,
    Monitor,
    Quote,
    QuoteObservation,
    SearchRun,
)

ALERTABLE_RUN_STATUSES = {
    RunStatus.SUCCEEDED.value,
    RunStatus.PARTIALLY_SUCCEEDED.value,
}


def evaluate_alerts_for_run(
    session: Session,
    *,
    run_id: str,
    default_cooldown_minutes: int,
    evaluated_at: datetime | None = None,
) -> list[str]:
    now = evaluated_at or datetime.now(UTC)
    run = session.scalar(
        select(SearchRun)
        .where(SearchRun.id == run_id)
        .options(
            joinedload(SearchRun.monitor).selectinload(Monitor.alert_rules),
        )
    )
    if run is None or run.status not in ALERTABLE_RUN_STATUSES:
        return []

    observations = list(
        session.scalars(
            select(QuoteObservation)
            .where(QuoteObservation.search_run_id == run.id)
            .options(joinedload(QuoteObservation.quote).joinedload(Quote.itinerary))
        ).all()
    )
    if not observations:
        return []
    cheapest = min(
        observations,
        key=lambda item: (item.price_minor, item.observed_at, item.id),
    )
    previous_low = session.scalar(
        select(func.min(QuoteObservation.price_minor))
        .join(SearchRun, SearchRun.id == QuoteObservation.search_run_id)
        .where(
            SearchRun.monitor_id == run.monitor_id,
            QuoteObservation.search_run_id != run.id,
            QuoteObservation.currency == cheapest.currency,
        )
    )

    pending_event_ids: list[str] = []
    for rule in sorted(run.monitor.alert_rules, key=lambda item: item.id):
        if not rule.is_active:
            continue
        reason = _matching_reason(rule, cheapest, previous_low)
        if reason is None:
            continue
        deduplication_key = _deduplication_key(rule.id, run.id)
        existing = session.scalar(
            select(AlertEvent).where(AlertEvent.deduplication_key == deduplication_key)
        )
        if existing is not None:
            if existing.status == AlertEventStatus.PENDING.value:
                pending_event_ids.append(existing.id)
            continue

        cooldown_minutes = _cooldown_minutes(rule, default_cooldown_minutes)
        cooldown_active = _cooldown_is_active(
            session,
            rule_id=rule.id,
            cutoff=now - timedelta(minutes=cooldown_minutes),
        )
        event = AlertEvent(
            monitor_id=run.monitor_id,
            alert_rule_id=rule.id,
            search_run_id=run.id,
            quote_observation_id=cheapest.id,
            rule_type=rule.rule_type,
            deduplication_key=deduplication_key,
            status=(
                AlertEventStatus.SUPPRESSED.value
                if cooldown_active
                else AlertEventStatus.PENDING.value
            ),
            message=_render_message(run.monitor, cheapest, reason),
            suppression_reason=(
                f"cooldown active for {cooldown_minutes} minutes" if cooldown_active else None
            ),
        )
        try:
            with session.begin_nested():
                session.add(event)
                session.flush()
        except IntegrityError:
            existing = session.scalar(
                select(AlertEvent).where(AlertEvent.deduplication_key == deduplication_key)
            )
            if existing is not None and existing.status == AlertEventStatus.PENDING.value:
                pending_event_ids.append(existing.id)
            continue
        if event.status == AlertEventStatus.PENDING.value:
            pending_event_ids.append(event.id)
    return pending_event_ids


def get_alert_event(session: Session, event_id: str) -> AlertEvent:
    event = session.get(AlertEvent, event_id)
    if event is None:
        raise AppError(
            code="ALERT_NOT_FOUND",
            message="Alert event not found.",
            status_code=404,
            details={"alert_event_id": event_id},
        )
    return event


def list_alert_events(
    session: Session,
    *,
    page: int,
    page_size: int,
    monitor_id: str | None = None,
    status: AlertEventStatus | None = None,
) -> tuple[list[AlertEvent], int]:
    filters = []
    if monitor_id is not None:
        filters.append(AlertEvent.monitor_id == monitor_id)
    if status is not None:
        filters.append(AlertEvent.status == status.value)
    total = session.scalar(select(func.count()).select_from(AlertEvent).where(*filters)) or 0
    events = list(
        session.scalars(
            select(AlertEvent)
            .where(*filters)
            .order_by(AlertEvent.created_at.desc(), AlertEvent.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return events, total


def alert_event_to_read(event: AlertEvent) -> AlertEventRead:
    return AlertEventRead(
        id=event.id,
        monitor_id=event.monitor_id,
        alert_rule_id=event.alert_rule_id,
        search_run_id=event.search_run_id,
        quote_observation_id=event.quote_observation_id,
        rule_type=event.rule_type,
        status=event.status,
        message=event.message,
        provider=event.provider,
        provider_message_id=event.provider_message_id,
        attempt_count=event.attempt_count,
        last_attempt_at=event.last_attempt_at,
        suppression_reason=event.suppression_reason,
        error_message=event.error_message,
        created_at=event.created_at,
        sent_at=event.sent_at,
    )


def _matching_reason(
    rule: AlertRule,
    observation: QuoteObservation,
    previous_low: int | None,
) -> str | None:
    if rule.rule_type == "price_below_limit":
        limit = rule.configuration.get("price_minor")
        if isinstance(limit, bool) or not isinstance(limit, int):
            return None
        if observation.price_minor <= limit:
            return f"Price is at or below {_format_money(limit, observation.currency)}"
        return None
    if rule.rule_type == "new_historical_low":
        if previous_low is not None and observation.price_minor < previous_low:
            formatted_previous_low = _format_money(previous_low, observation.currency)
            return f"New historical low; previous low was {formatted_previous_low}"
        return None
    return None


def _cooldown_minutes(rule: AlertRule, default: int) -> int:
    configured = rule.configuration.get("cooldown_minutes", default)
    if isinstance(configured, bool) or not isinstance(configured, int):
        return default
    return max(0, int(configured))


def _cooldown_is_active(session: Session, *, rule_id: str, cutoff: datetime) -> bool:
    return (
        session.scalar(
            select(AlertEvent.id)
            .where(
                AlertEvent.alert_rule_id == rule_id,
                AlertEvent.status == AlertEventStatus.SENT.value,
                AlertEvent.sent_at.is_not(None),
                AlertEvent.sent_at >= cutoff,
            )
            .limit(1)
        )
        is not None
    )


def _deduplication_key(rule_id: str, run_id: str) -> str:
    return hashlib.sha256(f"alert:v1:{rule_id}:{run_id}".encode()).hexdigest()


def _format_money(amount_minor: int, currency: str) -> str:
    return f"{currency} {minor_to_decimal(amount_minor, currency):f}"


def _render_message(
    monitor: Monitor,
    observation: QuoteObservation,
    reason: str,
) -> str:
    quote = observation.quote
    itinerary = quote.itinerary
    lines = [
        "FareBeacon price alert",
        f"Monitor: {monitor.name}",
        f"Route: {monitor.origin_iata} -> {monitor.destination_iata}",
        f"Price: {_format_money(observation.price_minor, observation.currency)}",
        f"Reason: {reason}",
        f"Departure: {itinerary.departure_at.astimezone(UTC):%Y-%m-%d %H:%M UTC}",
        f"Stops: {itinerary.stops}",
        f"Source: {quote.source_name}",
    ]
    if quote.booking_url:
        lines.append(f"Booking: {quote.booking_url}")
    return "\n".join(lines)[:4000]
