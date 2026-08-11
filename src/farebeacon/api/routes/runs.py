from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from farebeacon.api.dependencies import (
    get_db,
    pagination,
    require_authentication,
    require_idempotency_key,
)
from farebeacon.api.errors import AppError
from farebeacon.api.responses import success
from farebeacon.api.schemas import ApiResponse, PageData, RunQueued, RunRead
from farebeacon.application.runs import (
    create_search_run,
    get_search_run,
    list_search_runs,
    run_to_read,
)
from farebeacon.domain.enums import RunStatus
from farebeacon.tasks.orchestration import orchestrate_run

router = APIRouter(tags=["runs"], dependencies=[Depends(require_authentication)])


@router.post(
    "/api/v1/monitors/{monitor_id}/runs",
    response_model=ApiResponse[RunQueued],
    status_code=status.HTTP_202_ACCEPTED,
)
def post_monitor_run(
    request: Request,
    monitor_id: str,
    session: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> object:
    run, created = create_search_run(
        session,
        monitor_id=monitor_id,
        idempotency_key=idempotency_key,
    )
    queued_response = RunQueued(run_id=run.id, status=run.status)
    if created:
        try:
            orchestrate_run.apply_async(args=[run.id], queue="orchestration")
        except Exception as exc:
            run.status = RunStatus.FAILED.value
            run.finished_at = datetime.now(UTC)
            run.error_summary = {
                "code": "SOURCE_TEMPORARILY_UNAVAILABLE",
                "message": "The task broker did not accept the run.",
            }
            session.commit()
            raise AppError(
                code="SOURCE_TEMPORARILY_UNAVAILABLE",
                message="The task broker is temporarily unavailable.",
                status_code=503,
                details={"run_id": run.id, "retryable": True},
            ) from exc
    return success(request, queued_response)


@router.get("/api/v1/runs", response_model=ApiResponse[PageData[RunRead]])
def get_runs(
    request: Request,
    session: Annotated[Session, Depends(get_db)],
    page_params: Annotated[tuple[int, int], Depends(pagination)],
) -> object:
    page, page_size = page_params
    runs, total = list_search_runs(session, page=page, page_size=page_size)
    return success(
        request,
        PageData(
            items=[run_to_read(run) for run in runs],
            page=page,
            page_size=page_size,
            total=total,
        ),
    )


@router.get("/api/v1/runs/{run_id}", response_model=ApiResponse[RunRead])
def get_run_by_id(
    request: Request,
    run_id: str,
    session: Annotated[Session, Depends(get_db)],
) -> object:
    return success(request, run_to_read(get_search_run(session, run_id)))
