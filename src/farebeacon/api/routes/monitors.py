from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from farebeacon.api.dependencies import (
    get_db,
    pagination,
    require_authentication,
    require_idempotency_key,
)
from farebeacon.api.responses import success
from farebeacon.api.schemas import (
    COMMON_ERROR_RESPONSES,
    ApiResponse,
    MonitorCreate,
    MonitorRead,
    PageData,
)
from farebeacon.application.monitors import (
    create_monitor,
    get_monitor,
    list_monitors,
    monitor_to_read,
)
from farebeacon.sources.registry import get_source_registry

router = APIRouter(
    prefix="/api/v1/monitors",
    tags=["monitors"],
    dependencies=[Depends(require_authentication)],
    responses=COMMON_ERROR_RESPONSES,
)


@router.post("", response_model=ApiResponse[MonitorRead], status_code=status.HTTP_201_CREATED)
def post_monitor(
    request: Request,
    payload: MonitorCreate,
    session: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> object:
    monitor, _created = create_monitor(
        session,
        payload=payload,
        idempotency_key=idempotency_key,
        registry=get_source_registry(),
    )
    return success(request, monitor_to_read(monitor))


@router.get("", response_model=ApiResponse[PageData[MonitorRead]])
def get_monitors(
    request: Request,
    session: Annotated[Session, Depends(get_db)],
    page_params: Annotated[tuple[int, int], Depends(pagination)],
) -> object:
    page, page_size = page_params
    monitors, total = list_monitors(session, page=page, page_size=page_size)
    return success(
        request,
        PageData(
            items=[monitor_to_read(monitor) for monitor in monitors],
            page=page,
            page_size=page_size,
            total=total,
        ),
    )


@router.get("/{monitor_id}", response_model=ApiResponse[MonitorRead])
def get_monitor_by_id(
    request: Request,
    monitor_id: str,
    session: Annotated[Session, Depends(get_db)],
) -> object:
    return success(request, monitor_to_read(get_monitor(session, monitor_id)))
