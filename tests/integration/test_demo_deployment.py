from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from farebeacon.api.main import create_app
from farebeacon.config import Settings
from farebeacon.infrastructure.db.session import database
from farebeacon.scripts.seed_demo import seed

DEMO_TOKEN = "demo-token-with-at-least-thirty-two-characters"


@pytest.fixture
def demo_client() -> Iterator[TestClient]:
    settings = Settings(
        api_token=DEMO_TOKEN,
        demo_read_only=True,
        celery_task_always_eager=True,
        notification_backend="disabled",
    )
    with TestClient(create_app(settings=settings, app_database=database)) as client:
        yield client


def test_demo_mode_serves_reads_without_a_token(demo_client: TestClient) -> None:
    response = demo_client.get("/api/v1/monitors")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["items"] == []


def test_demo_mode_still_protects_writes(demo_client: TestClient) -> None:
    response = demo_client.post(
        "/api/v1/monitors",
        headers={"Idempotency-Key": "demo-unauthenticated-write"},
        json={
            "name": "Should not be created",
            "route": {"origin": "BSB", "destination": "PVH"},
            "departure_dates": ["2030-07-10"],
            "sources": ["mock"],
        },
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_readiness_skips_redis_when_the_broker_does_not_need_it(demo_client: TestClient) -> None:
    response = demo_client.get("/ready")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["checks"] == {"database": "ok"}


def test_seed_is_idempotent_and_produces_history_and_alerts(demo_client: TestClient) -> None:
    with database.session() as session:
        first = seed(session)
    with database.session() as session:
        second = seed(session)
    assert first == second

    monitors = demo_client.get("/api/v1/monitors").json()["data"]
    assert monitors["total"] == len(first)

    history = demo_client.get(f"/api/v1/monitors/{first[0]}/price-history").json()["data"]
    assert history["total"] > 4

    alerts = demo_client.get(f"/api/v1/alerts?monitor_id={first[0]}").json()["data"]
    assert alerts["total"] >= 1
    assert "new_historical_low" in {item["rule_type"] for item in alerts["items"]}
