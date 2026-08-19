"""Server-rendered read-only interface.

The pages render from the same application services the HTTP API exposes, rather than calling that
API over HTTP from inside the same process. The API remains the only public integration surface;
this layer is a reader of the same functions, and a serverless deployment would otherwise pay a
second function invocation to talk to itself.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from farebeacon.api.dependencies import get_db
from farebeacon.api.schemas import PriceHistoryRead
from farebeacon.application.alerts import alert_event_to_read, list_alert_events
from farebeacon.application.monitors import get_monitor, list_monitors, monitor_to_read
from farebeacon.application.results import list_latest_offers, list_price_history
from farebeacon.domain.money import minor_to_decimal

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
HISTORY_PAGE_SIZE = 10
OFFER_PAGE_SIZE = 10

router = APIRouter(include_in_schema=False)


@router.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    session: Annotated[Session, Depends(get_db)],
) -> Any:
    monitors, total = list_monitors(session, page=1, page_size=20)
    cards = []
    for monitor in monitors:
        offers, _ = list_latest_offers(session, monitor_id=monitor.id, page=1, page_size=1)
        cheapest = offers[0] if offers else None
        cards.append(
            {
                "monitor": monitor_to_read(monitor),
                "cheapest": _money(cheapest.price_minor, cheapest.currency) if cheapest else None,
                "observed_at": cheapest.observed_at if cheapest else None,
                "source": cheapest.source_name if cheapest else None,
            }
        )
    return TEMPLATES.TemplateResponse(
        request=request,
        name="index.html",
        context={"cards": cards, "total": total},
    )


@router.get("/monitors/{monitor_id}", response_class=HTMLResponse)
def monitor_detail(
    monitor_id: str,
    request: Request,
    session: Annotated[Session, Depends(get_db)],
) -> Any:
    monitor = monitor_to_read(get_monitor(session, monitor_id))
    offers, offers_total = list_latest_offers(
        session, monitor_id=monitor_id, page=1, page_size=OFFER_PAGE_SIZE
    )
    events, _ = list_alert_events(session, page=1, page_size=10, monitor_id=monitor_id)
    return TEMPLATES.TemplateResponse(
        request=request,
        name="monitor.html",
        context={
            "monitor": monitor,
            "offers": [
                {
                    "offer": offer,
                    "price": _money(offer.price_minor, offer.currency),
                    "duration": _duration(offer.duration_minutes),
                }
                for offer in offers
            ],
            "offers_total": offers_total,
            "alerts": [alert_event_to_read(event) for event in events],
            "history": _history(session, monitor_id=monitor_id, page=1),
        },
    )


@router.get("/monitors/{monitor_id}/price-history", response_class=HTMLResponse)
def price_history_fragment(
    monitor_id: str,
    request: Request,
    session: Annotated[Session, Depends(get_db)],
    page: int = 1,
) -> Any:
    """Return the price-history panel alone, so the page can page through it in place."""
    return TEMPLATES.TemplateResponse(
        request=request,
        name="_price_history.html",
        context={
            "monitor_id": monitor_id,
            "history": _history(session, monitor_id=monitor_id, page=max(page, 1)),
        },
    )


def _history(session: Session, *, monitor_id: str, page: int) -> dict[str, Any]:
    observations, total = list_price_history(
        session, monitor_id=monitor_id, page=page, page_size=HISTORY_PAGE_SIZE
    )
    ordered = sorted(observations, key=lambda item: item.observed_at)
    return {
        "points": [
            {
                "observation": observation,
                "price": _money(observation.price_minor, observation.currency),
            }
            for observation in reversed(ordered)
        ],
        "chart": _chart(ordered),
        "total": total,
        "page": page,
        "pages": max(1, -(-total // HISTORY_PAGE_SIZE)),
    }


def _chart(observations: list[PriceHistoryRead]) -> dict[str, Any] | None:
    """Lay out a sparkline for the observed prices, in chart coordinates."""
    if len(observations) < 2:
        return None
    prices = [observation.price_minor for observation in observations]
    lowest, highest = min(prices), max(prices)
    span = highest - lowest or 1
    width, height = 640, 160
    step = width / (len(prices) - 1)
    points = [
        (round(index * step, 2), round(height - ((price - lowest) / span) * (height - 20) - 10, 2))
        for index, price in enumerate(prices)
    ]
    currency = observations[0].currency
    return {
        "polyline": " ".join(f"{x},{y}" for x, y in points),
        "area": f"0,{height} " + " ".join(f"{x},{y}" for x, y in points) + f" {width},{height}",
        "width": width,
        "height": height,
        "lowest": _money(lowest, currency),
        "highest": _money(highest, currency),
        "first_at": observations[0].observed_at,
        "last_at": observations[-1].observed_at,
        "dropped": prices[-1] < prices[0],
    }


def _money(amount_minor: int, currency: str) -> str:
    value: Decimal = minor_to_decimal(amount_minor, currency)
    return f"{currency} {value:,.2f}"


def _duration(minutes: int) -> str:
    hours, remainder = divmod(minutes, 60)
    return f"{hours}h {remainder:02d}m" if hours else f"{remainder}m"
