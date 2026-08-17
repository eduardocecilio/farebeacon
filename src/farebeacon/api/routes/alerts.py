from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from farebeacon.api.dependencies import get_db, pagination, require_authentication
from farebeacon.api.responses import success
from farebeacon.api.schemas import COMMON_ERROR_RESPONSES, AlertEventRead, ApiResponse, PageData
from farebeacon.application.alerts import (
    alert_event_to_read,
    get_alert_event,
    list_alert_events,
)
from farebeacon.domain.enums import AlertEventStatus

router = APIRouter(
    prefix="/api/v1/alerts",
    tags=["alerts"],
    dependencies=[Depends(require_authentication)],
    responses=COMMON_ERROR_RESPONSES,
)


@router.get("", response_model=ApiResponse[PageData[AlertEventRead]])
def get_alerts(
    request: Request,
    session: Annotated[Session, Depends(get_db)],
    page_params: Annotated[tuple[int, int], Depends(pagination)],
    monitor_id: str | None = None,
    status: AlertEventStatus | None = None,
) -> object:
    page, page_size = page_params
    events, total = list_alert_events(
        session,
        page=page,
        page_size=page_size,
        monitor_id=monitor_id,
        status=status,
    )
    return success(
        request,
        PageData(
            items=[alert_event_to_read(event) for event in events],
            page=page,
            page_size=page_size,
            total=total,
        ),
    )


@router.get("/{event_id}", response_model=ApiResponse[AlertEventRead])
def get_alert_by_id(
    request: Request,
    event_id: str,
    session: Annotated[Session, Depends(get_db)],
) -> object:
    return success(request, alert_event_to_read(get_alert_event(session, event_id)))
