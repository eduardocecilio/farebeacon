from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_ROOT = Path(".test")
TEST_ROOT.mkdir(exist_ok=True)
os.environ["FAREBEACON_ENV"] = "test"
os.environ["FAREBEACON_API_TOKEN"] = "test-token-with-at-least-thirty-two-characters"
os.environ["FAREBEACON_DATABASE_URL"] = "sqlite+pysqlite:///./.test/farebeacon.db"
os.environ["FAREBEACON_REDIS_URL"] = "redis://127.0.0.1:6379/15"
os.environ["FAREBEACON_ARTIFACTS_ROOT"] = ".test/artifacts"
os.environ["FAREBEACON_CELERY_TASK_ALWAYS_EAGER"] = "true"

from farebeacon.api.main import app
from farebeacon.application.common import sync_source_definitions
from farebeacon.infrastructure.db.models import Base
from farebeacon.infrastructure.db.session import database
from farebeacon.sources.registry import get_source_registry


@pytest.fixture(autouse=True)
def reset_database() -> Iterator[None]:
    Base.metadata.drop_all(database.engine)
    Base.metadata.create_all(database.engine)
    with database.session() as session:
        sync_source_definitions(session, get_source_registry())
        session.commit()
    yield


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token-with-at-least-thirty-two-characters"}


@pytest.fixture
def monitor_payload() -> dict[str, object]:
    return {
        "name": "Brasília para Porto Velho",
        "route": {"origin": "BSB", "destination": "PVH"},
        "departure_dates": ["2030-07-10", "2030-07-11"],
        "passengers": {"adults": 1, "children": 0, "infants": 0},
        "filters": {"currency": "BRL", "max_stops": 1, "max_price_minor": 100000},
        "sources": ["mock"],
        "schedule": {"interval_minutes": 720},
        "alerts": {"new_historical_low": True, "price_below_minor": 100000},
    }
