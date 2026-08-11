from __future__ import annotations

from datetime import UTC, datetime

from celery import chain  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from farebeacon.application.common import query_fingerprint
from farebeacon.domain.enums import RunStatus, SourceRunStatus
from farebeacon.infrastructure.db.models import Monitor, SearchRun, SourceRun
from farebeacon.infrastructure.db.session import database
from farebeacon.sources.registry import get_source_registry
from farebeacon.tasks.celery_app import celery_app

TERMINAL_RUN_STATUSES = {
    RunStatus.SUCCEEDED.value,
    RunStatus.PARTIALLY_SUCCEEDED.value,
    RunStatus.FAILED.value,
    RunStatus.CANCELLED.value,
}


@celery_app.task(name="farebeacon.orchestrate_run")  # type: ignore[untyped-decorator]
def orchestrate_run(run_id: str) -> dict[str, object]:
    with database.session() as session:
        run = session.scalar(
            select(SearchRun)
            .where(SearchRun.id == run_id)
            .options(
                selectinload(SearchRun.monitor).selectinload(Monitor.sources),
                selectinload(SearchRun.source_runs),
            )
        )
        if run is None:
            return {"run_id": run_id, "status": "missing"}
        if run.status in TERMINAL_RUN_STATUSES:
            return {"run_id": run_id, "status": run.status}

        enabled_sources = sorted(
            (source for source in run.monitor.sources if source.is_enabled),
            key=lambda source: source.priority,
        )
        if not enabled_sources:
            run.status = RunStatus.FAILED.value
            run.error_summary = {
                "code": "SOURCE_DISABLED",
                "message": "No source is enabled.",
            }
            run.finished_at = datetime.now(UTC)
            session.commit()
            return {"run_id": run_id, "status": run.status}

        registry = get_source_registry()
        existing_by_source = {item.source_name: item for item in run.source_runs}
        for monitor_source in enabled_sources:
            if monitor_source.source_name in existing_by_source:
                continue
            registered = registry.get(monitor_source.source_name)
            fingerprint = query_fingerprint(
                {
                    "source": monitor_source.source_name,
                    "origin": run.monitor.origin_iata,
                    "destination": run.monitor.destination_iata,
                    "departure_dates": run.monitor.departure_dates,
                    "return_dates": run.monitor.return_dates,
                    "adults": run.monitor.adults,
                    "children": run.monitor.children,
                    "infants": run.monitor.infants,
                    "cabin_class": run.monitor.cabin_class,
                    "currency": run.monitor.currency,
                    "max_stops": run.monitor.max_stops,
                    "market": "BR",
                    "locale": "pt-BR",
                }
            )
            source_run = SourceRun(
                search_run_id=run.id,
                source_name=monitor_source.source_name,
                source_kind=registered.source.kind.value,
                status=SourceRunStatus.QUEUED.value,
                request_fingerprint=fingerprint,
                parser_version=registered.parser.version,
            )
            session.add(source_run)
            session.flush()
            existing_by_source[source_run.source_name] = source_run

        run.status = RunStatus.RUNNING.value
        run.started_at = run.started_at or datetime.now(UTC)
        run.sources_requested = len(existing_by_source)
        session.commit()
        queued_ids = [
            item.id
            for item in existing_by_source.values()
            if item.status == SourceRunStatus.QUEUED.value
        ]

    from farebeacon.tasks.normalization import normalize_source_results
    from farebeacon.tasks.sources import execute_source_run

    for source_run_id in queued_ids:
        workflow = chain(
            execute_source_run.s(source_run_id).set(queue="source.mock"),
            normalize_source_results.s(source_run_id).set(queue="normalize"),
        )
        workflow.apply_async()
    return {
        "run_id": run_id,
        "status": RunStatus.RUNNING.value,
        "sources": len(queued_ids),
    }
