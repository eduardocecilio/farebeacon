"""Seed a public demo database with deterministic MockSource data.

The script is idempotent: it reuses fixed idempotency keys, so running it again against the same
database returns the existing monitors and runs instead of duplicating them. It is meant for the
read-only demo deployment described in docs/vercel-demo.md, never for a database that owns real
history.

Each monitor is executed several times with the source price moving between runs, which is what
gives the demo a price history with a visible shape rather than a straight line, and produces real
`new_historical_low` and `price_below_limit` alert events along the way.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from farebeacon.api.schemas import MonitorCreate
from farebeacon.application.monitors import create_monitor
from farebeacon.application.runs import create_search_run
from farebeacon.domain.enums import RunTrigger
from farebeacon.infrastructure.db.models import MonitorSource, QuoteObservation, SearchRun
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

# Applied to the source price between runs, in minor units. A fare that only falls looks synthetic;
# one that rises before falling further is what a monitor is actually for.
PRICE_STEPS_MINOR = (-9000, +4500, -14000, -6500)
# Seeding runs in milliseconds, which would stamp every observation with the same minute and leave
# the price history without a time axis. The observations are restamped one day apart afterwards.
# The data is seeded, not observed: the spacing is as synthetic as the prices MockSource returns.
RUN_INTERVAL = timedelta(days=1)


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
        price = int(payload["source_configuration"]["mock"]["base_price_minor"])
        for step, delta in enumerate(PRICE_STEPS_MINOR):
            price = max(price + delta, 1000)
            _set_source_price(session, monitor_id=monitor.id, price_minor=price)
            _execute_run(session, monitor_id=monitor.id, key=f"demo-seed-run-{index}-step-{step}")
        _spread_observations_over_time(session, monitor_id=monitor.id)
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


def _set_source_price(session: Session, *, monitor_id: str, price_minor: int) -> None:
    """Move the source price, the way a real fare moves between two checks."""
    monitor_source = session.scalar(
        select(MonitorSource).where(MonitorSource.monitor_id == monitor_id)
    )
    if monitor_source is None:
        return
    monitor_source.configuration = {
        **monitor_source.configuration,
        "base_price_minor": price_minor,
    }
    session.commit()


def _spread_observations_over_time(session: Session, *, monitor_id: str) -> None:
    """Restamp each run's observations one interval apart, ending now."""
    run_ids = list(
        session.scalars(
            select(SearchRun.id)
            .where(SearchRun.monitor_id == monitor_id)
            .order_by(SearchRun.created_at, SearchRun.id)
        ).all()
    )
    now = datetime.now(UTC)
    for position, run_id in enumerate(reversed(run_ids)):
        observed_at = now - RUN_INTERVAL * position
        for observation in session.scalars(
            select(QuoteObservation).where(QuoteObservation.search_run_id == run_id)
        ).all():
            observation.observed_at = observed_at
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
