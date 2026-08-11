from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from farebeacon.api.dependencies import get_db, pagination, require_authentication
from farebeacon.api.responses import success
from farebeacon.api.schemas import ApiResponse, OfferRead, PageData, PriceHistoryRead
from farebeacon.application.results import list_latest_offers, list_price_history

router = APIRouter(
    prefix="/api/v1/monitors/{monitor_id}",
    tags=["results"],
    dependencies=[Depends(require_authentication)],
)


@router.get("/offers", response_model=ApiResponse[PageData[OfferRead]])
def get_offers(
    request: Request,
    monitor_id: str,
    session: Annotated[Session, Depends(get_db)],
    page_params: Annotated[tuple[int, int], Depends(pagination)],
) -> object:
    page, page_size = page_params
    offers, total = list_latest_offers(
        session,
        monitor_id=monitor_id,
        page=page,
        page_size=page_size,
    )
    return success(
        request,
        PageData(items=offers, page=page, page_size=page_size, total=total),
    )


@router.get("/price-history", response_model=ApiResponse[PageData[PriceHistoryRead]])
def get_price_history(
    request: Request,
    monitor_id: str,
    session: Annotated[Session, Depends(get_db)],
    page_params: Annotated[tuple[int, int], Depends(pagination)],
) -> object:
    page, page_size = page_params
    history, total = list_price_history(
        session,
        monitor_id=monitor_id,
        page=page,
        page_size=page_size,
    )
    return success(
        request,
        PageData(items=history, page=page, page_size=page_size, total=total),
    )
