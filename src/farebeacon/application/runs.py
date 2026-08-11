from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from farebeacon.api.errors import AppError
from farebeacon.api.schemas import RunRead, SourceRunRead
from farebeacon.application.common import (
    idempotency_lookup,
    make_idempotency_record,
    request_digest,
)
from farebeacon.application.monitors import get_monitor
from farebeacon.domain.enums import RunStatus, RunTrigger
from farebeacon.infrastructure.db.models import SearchRun

ACTIVE_RUN_STATUSES = (RunStatus.QUEUED.value, RunStatus.RUNNING.value)


def create_search_run(
    session: Session,
    *,
    monitor_id: str,
    idempotency_key: str,
    trigger: RunTrigger = RunTrigger.MANUAL,
) -> tuple[SearchRun, bool]:
    scope = f"POST:/api/v1/monitors/{monitor_id}/runs"
    payload_hash = request_digest({"monitor_id": monitor_id, "trigger": trigger.value})
    existing = idempotency_lookup(
        session,
        scope=scope,
        key=idempotency_key,
        request_hash=payload_hash,
    )
    if existing is not None:
        return get_search_run(session, existing.resource_id), False

    monitor = get_monitor(session, monitor_id)
    if not monitor.is_active:
        raise AppError(
            code="VALIDATION_ERROR",
            message="A paused monitor cannot be executed.",
            status_code=409,
            details={"monitor_id": monitor_id},
        )
    active_run_id = session.scalar(
        select(SearchRun.id).where(
            SearchRun.monitor_id == monitor_id,
            SearchRun.status.in_(ACTIVE_RUN_STATUSES),
        )
    )
    if active_run_id is not None:
        raise AppError(
            code="RUN_ALREADY_ACTIVE",
            message="This monitor already has an active run.",
            status_code=409,
            details={"run_id": active_run_id},
        )

    run = SearchRun(monitor_id=monitor_id, trigger=trigger.value, status=RunStatus.QUEUED.value)
    session.add(run)
    session.flush()
    session.add(
        make_idempotency_record(
            scope=scope,
            key=idempotency_key,
            request_hash=payload_hash,
            resource_type="search_run",
            resource_id=run.id,
            response_status=202,
            response_body={"run_id": run.id, "status": run.status},
        )
    )
    session.commit()
    return get_search_run(session, run.id), True


def get_search_run(session: Session, run_id: str) -> SearchRun:
    run = session.scalar(
        select(SearchRun).where(SearchRun.id == run_id).options(selectinload(SearchRun.source_runs))
    )
    if run is None:
        raise AppError(
            code="RUN_NOT_FOUND",
            message="Search run not found.",
            status_code=404,
            details={"run_id": run_id},
        )
    return run


def list_search_runs(
    session: Session,
    *,
    page: int,
    page_size: int,
) -> tuple[list[SearchRun], int]:
    total = session.scalar(select(func.count()).select_from(SearchRun)) or 0
    runs = list(
        session.scalars(
            select(SearchRun)
            .options(selectinload(SearchRun.source_runs))
            .order_by(SearchRun.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return runs, total


def run_to_read(run: SearchRun) -> RunRead:
    return RunRead(
        id=run.id,
        monitor_id=run.monitor_id,
        trigger=run.trigger,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        offers_received=run.offers_received,
        sources_requested=run.sources_requested,
        sources_succeeded=run.sources_succeeded,
        sources_failed=run.sources_failed,
        error_summary=run.error_summary,
        created_at=run.created_at,
        source_runs=[
            SourceRunRead(
                id=source_run.id,
                source_name=source_run.source_name,
                source_kind=source_run.source_kind,
                status=source_run.status,
                started_at=source_run.started_at,
                finished_at=source_run.finished_at,
                quota_cost=source_run.quota_cost,
                error_code=source_run.error_code,
                error_message=source_run.error_message,
            )
            for source_run in sorted(run.source_runs, key=lambda item: item.source_name)
        ],
    )
