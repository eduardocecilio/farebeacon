from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from farebeacon.config import get_settings
from farebeacon.domain.exceptions import DomainError
from farebeacon.domain.sources import SearchQuery, SourceExecutionContext
from farebeacon.infrastructure.db.models import Monitor, SearchRun, SourceRun
from farebeacon.infrastructure.db.session import database
from farebeacon.sources.registry import get_source_registry
from farebeacon.tasks.celery_app import celery_app
from farebeacon.tasks.serialization import serialize_batch


@celery_app.task(name="farebeacon.execute_source_run")  # type: ignore[untyped-decorator]
def execute_source_run(source_run_id: str) -> dict[str, Any]:
    with database.session() as session:
        source_run = session.scalar(
            select(SourceRun)
            .where(SourceRun.id == source_run_id)
            .options(
                joinedload(SourceRun.search_run)
                .joinedload(SearchRun.monitor)
                .selectinload(Monitor.sources)
            )
        )
        if source_run is None:
            return _failure("SOURCE_RUN_NOT_FOUND", "Source run no longer exists.", False)
        if source_run.status == "succeeded":
            return {"status": "already_persisted", "batches": []}

        source_run.status = "running"
        source_run.started_at = source_run.started_at or source_run.search_run.started_at
        session.commit()
        run = source_run.search_run
        monitor = run.monitor
        monitor_source = next(
            source for source in monitor.sources if source.source_name == source_run.source_name
        )
        registered = get_source_registry().get(source_run.source_name)
        queries = _expand_queries(monitor)
        context = SourceExecutionContext(
            run_id=run.id,
            source_run_id=source_run.id,
            timeout_seconds=get_settings().default_source_timeout_seconds,
            correlation_id=run.id,
            configuration=monitor_source.configuration,
        )

    try:
        batches = asyncio.run(_fetch_all(registered.source, queries, context))
    except DomainError as error:
        return _failure(
            getattr(error, "code", "SOURCE_TEMPORARILY_UNAVAILABLE"),
            str(error),
            bool(getattr(error, "retryable", False)),
        )
    except Exception:
        logging.getLogger("farebeacon.sources").exception(
            "source adapter failed unexpectedly",
            extra={"source_run_id": source_run_id},
        )
        return _failure(
            "SOURCE_TEMPORARILY_UNAVAILABLE",
            "The source failed unexpectedly.",
            True,
        )

    return {
        "status": "fetched",
        "batches": [serialize_batch(batch) for batch in batches],
    }


async def _fetch_all(
    source: Any,
    queries: list[SearchQuery],
    context: SourceExecutionContext,
) -> list[Any]:
    batches = []
    for query in queries:
        batches.append(
            await asyncio.wait_for(source.fetch(query, context), context.timeout_seconds)
        )
    return batches


def _expand_queries(monitor: Any) -> list[SearchQuery]:
    return_dates = monitor.return_dates or [None] * len(monitor.departure_dates)
    return [
        SearchQuery(
            origin=monitor.origin_iata,
            destination=monitor.destination_iata,
            departure_date=date.fromisoformat(departure),
            return_date=date.fromisoformat(returned) if returned else None,
            adults=monitor.adults,
            children=monitor.children,
            infants=monitor.infants,
            cabin_class=monitor.cabin_class,
            currency=monitor.currency,
            max_stops=monitor.max_stops,
        )
        for departure, returned in zip(monitor.departure_dates, return_dates, strict=True)
    ]


def _failure(code: str, message: str, retryable: bool) -> dict[str, Any]:
    return {
        "status": "failed",
        "error": {"code": code, "message": message, "retryable": retryable},
        "batches": [],
    }
