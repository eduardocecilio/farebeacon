from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from farebeacon.api.errors import AppError
from farebeacon.api.schemas import MonitorCreate, MonitorRead
from farebeacon.application.common import (
    idempotency_lookup,
    make_idempotency_record,
    request_digest,
    sync_source_definitions,
)
from farebeacon.domain.enums import TripType
from farebeacon.infrastructure.db.models import (
    AlertRule,
    Monitor,
    MonitorSource,
    SourceDefinition,
)
from farebeacon.sources.registry import SourceRegistry


def create_monitor(
    session: Session,
    *,
    payload: MonitorCreate,
    idempotency_key: str,
    registry: SourceRegistry,
) -> tuple[Monitor, bool]:
    scope = "POST:/api/v1/monitors"
    payload_hash = request_digest(payload.model_dump(mode="json"))
    existing = idempotency_lookup(
        session,
        scope=scope,
        key=idempotency_key,
        request_hash=payload_hash,
    )
    if existing is not None:
        monitor = get_monitor(session, existing.resource_id)
        return monitor, False

    sync_source_definitions(session, registry)
    session.flush()
    for source_name in payload.sources:
        try:
            registry.get(source_name)
        except KeyError as exc:
            raise AppError(
                code="SOURCE_NOT_FOUND",
                message="The requested source is not installed.",
                status_code=404,
                details={"source": source_name},
            ) from exc
        definition = session.get(SourceDefinition, source_name)
        if definition is None or not definition.is_enabled:
            raise AppError(
                code="SOURCE_DISABLED",
                message="The requested source is disabled.",
                status_code=409,
                details={"source": source_name},
            )

    trip_type = TripType.ROUND_TRIP if payload.return_dates else TripType.ONE_WAY
    monitor = Monitor(
        name=payload.name,
        origin_iata=payload.route.origin,
        destination_iata=payload.route.destination,
        departure_dates=[value.isoformat() for value in payload.departure_dates],
        return_dates=[value.isoformat() for value in payload.return_dates]
        if payload.return_dates
        else None,
        trip_type=trip_type.value,
        adults=payload.passengers.adults,
        children=payload.passengers.children,
        infants=payload.passengers.infants,
        cabin_class=payload.filters.cabin_class,
        currency=payload.filters.currency,
        max_price_minor=payload.filters.max_price_minor,
        max_stops=payload.filters.max_stops,
        departure_time_from=payload.filters.departure_time_from,
        departure_time_to=payload.filters.departure_time_to,
        check_interval_minutes=payload.schedule.interval_minutes,
        is_active=True,
        next_run_at=datetime.now(UTC) + timedelta(minutes=payload.schedule.interval_minutes),
    )
    for priority, source_name in enumerate(payload.sources):
        monitor.sources.append(
            MonitorSource(
                source_name=source_name,
                priority=priority,
                configuration=payload.source_configuration.get(source_name, {}),
            )
        )
    if payload.alerts.new_historical_low:
        monitor.alert_rules.append(
            AlertRule(rule_type="new_historical_low", configuration={}, is_active=True)
        )
    if payload.alerts.price_below_minor is not None:
        monitor.alert_rules.append(
            AlertRule(
                rule_type="price_below_limit",
                configuration={"price_minor": payload.alerts.price_below_minor},
                is_active=True,
            )
        )
    session.add(monitor)
    session.flush()
    session.add(
        make_idempotency_record(
            scope=scope,
            key=idempotency_key,
            request_hash=payload_hash,
            resource_type="monitor",
            resource_id=monitor.id,
            response_status=201,
            response_body={"monitor_id": monitor.id},
        )
    )
    session.commit()
    return get_monitor(session, monitor.id), True


def get_monitor(session: Session, monitor_id: str) -> Monitor:
    monitor = session.scalar(
        select(Monitor)
        .where(Monitor.id == monitor_id)
        .options(selectinload(Monitor.sources), selectinload(Monitor.alert_rules))
    )
    if monitor is None:
        raise AppError(
            code="MONITOR_NOT_FOUND",
            message="Monitor not found.",
            status_code=404,
            details={"monitor_id": monitor_id},
        )
    return monitor


def list_monitors(
    session: Session,
    *,
    page: int,
    page_size: int,
) -> tuple[list[Monitor], int]:
    total = session.scalar(select(func.count()).select_from(Monitor)) or 0
    monitors = list(
        session.scalars(
            select(Monitor)
            .options(selectinload(Monitor.sources))
            .order_by(Monitor.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return monitors, total


def monitor_to_read(monitor: Monitor) -> MonitorRead:
    return MonitorRead(
        id=monitor.id,
        name=monitor.name,
        origin_iata=monitor.origin_iata,
        destination_iata=monitor.destination_iata,
        departure_dates=monitor.departure_dates,
        return_dates=monitor.return_dates,
        trip_type=monitor.trip_type,
        adults=monitor.adults,
        children=monitor.children,
        infants=monitor.infants,
        cabin_class=monitor.cabin_class,
        currency=monitor.currency,
        max_price_minor=monitor.max_price_minor,
        max_stops=monitor.max_stops,
        check_interval_minutes=monitor.check_interval_minutes,
        is_active=monitor.is_active,
        next_run_at=monitor.next_run_at,
        sources=[
            item.source_name for item in sorted(monitor.sources, key=lambda item: item.priority)
        ],
        created_at=monitor.created_at,
        updated_at=monitor.updated_at,
    )
