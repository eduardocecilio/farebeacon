"""Seed a public demo database with deterministic MockSource data.

The script is idempotent: it reuses fixed idempotency keys, so running it again against the same
database returns the existing monitors and runs instead of duplicating them. It is meant for the
read-only demo deployment described in docs/vercel-demo.md, never for a database that owns real
history.

Each monitor is executed twice with a lower price on the second run, which is what gives the demo a
price history with more than one point and one `new_historical_low` alert event.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from farebeacon.api.schemas import MonitorCreate
from farebeacon.application.monitors import create_monitor
from farebeacon.application.runs import create_search_run
from farebeacon.domain.enums import RunTrigger
from farebeacon.infrastructure.db.models import MonitorSource
from farebeacon.infrastructure.db.session import database
from farebeacon.sources.registry import get_source_registry
from farebeacon.tasks.orchestration import orchestrate_run

LOGGER = logging.getLogger("farebeacon.seed_demo")

DEMO_MONITORS: tuple[dict[str, Any], ...] = (
    {
        "name": "Brasília para Porto Velho",
        "route": {"origin": "BSB", "destination": "PVH"},
        "departure_dates": ["2030-07-10", "2030-07-11"],
        "passengers": {"adults": 1, "children": 0, "infants": 0},
        "filters": {"currency": "BRL", "max_stops": 1, "max_price_minor": 200000},
        "sources": ["mock"],
        "source_configuration": {"mock": {"base_price_minor": 90000}},
        "schedule": {"interval_minutes": 720},
        "alerts": {"new_historical_low": True, "price_below_minor": 80000},
    },
    {
        "name": "São Paulo para Recife",
        "route": {"origin": "GRU", "destination": "REC"},
        "departure_dates": ["2030-09-05"],
        "passengers": {"adults": 2, "children": 0, "infants": 0},
        "filters": {"currency": "BRL", "max_stops": 1, "max_price_minor": 250000},
        "sources": ["mock"],
        "source_configuration": {"mock": {"base_price_minor": 120000}},
        "schedule": {"interval_minutes": 1440},
        "alerts": {"new_historical_low": True},
    },
)

PRICE_DROP_MINOR = 20000


def seed(session: Session) -> list[str]:
    registry = get_source_registry()
    monitor_ids: list[str] = []
    for index, payload in enumerate(DEMO_MONITORS):
        monitor, created = create_monitor(
            session,
            payload=MonitorCreate.model_validate(payload),
            idempotency_key=f"demo-seed-monitor-{index}",
            registry=registry,
        )
        monitor_ids.append(monitor.id)
        if not created:
            LOGGER.info("monitor already seeded", extra={"monitor_id": monitor.id})
            continue
        _execute_run(session, monitor_id=monitor.id, key=f"demo-seed-run-{index}-baseline")
        _apply_price_drop(session, monitor_id=monitor.id, payload=payload)
        _execute_run(session, monitor_id=monitor.id, key=f"demo-seed-run-{index}-drop")
    return monitor_ids


def _execute_run(session: Session, *, monitor_id: str, key: str) -> None:
    run, created = create_search_run(
        session,
        monitor_id=monitor_id,
        idempotency_key=key,
        trigger=RunTrigger.SCHEDULED,
    )
    if created:
        orchestrate_run.apply_async(args=[run.id], queue="orchestration")


def _apply_price_drop(session: Session, *, monitor_id: str, payload: dict[str, Any]) -> None:
    configuration = payload["source_configuration"]["mock"]
    dropped = int(configuration["base_price_minor"]) - PRICE_DROP_MINOR
    monitor_source = session.scalar(
        select(MonitorSource).where(MonitorSource.monitor_id == monitor_id)
    )
    if monitor_source is None:
        return
    monitor_source.configuration = {
        **monitor_source.configuration,
        "base_price_minor": dropped,
    }
    session.commit()


def main() -> None:
    logging.basicConfig(level="INFO", format="%(levelname)s %(name)s %(message)s")
    with database.session() as session:
        monitor_ids = seed(session)
    LOGGER.info("demo seed complete", extra={"monitors": len(monitor_ids)})
    for monitor_id in monitor_ids:
        print(monitor_id)


if __name__ == "__main__":
    main()
