from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from farebeacon.infrastructure.db.models import AlertEvent, MonitorSource
from farebeacon.infrastructure.db.session import database
from farebeacon.tasks.alerts import dispatch_alert_event


def create_monitor(
    client: TestClient,
    headers: dict[str, str],
    payload: dict[str, object],
) -> str:
    response = client.post(
        "/api/v1/monitors",
        headers={**headers, "Idempotency-Key": "monitor-complete-flow"},
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def test_complete_mock_source_flow(
    client: TestClient,
    auth_headers: dict[str, str],
    monitor_payload: dict[str, object],
) -> None:
    monitor_id = create_monitor(client, auth_headers, monitor_payload)
    run_headers = {**auth_headers, "Idempotency-Key": "first-manual-run"}
    response = client.post(f"/api/v1/monitors/{monitor_id}/runs", headers=run_headers)
    assert response.status_code == 202, response.text
    assert response.json()["data"]["status"] == "queued"
    run_id = response.json()["data"]["run_id"]

    run = client.get(f"/api/v1/runs/{run_id}", headers=auth_headers)
    assert run.status_code == 200
    assert run.json()["data"]["status"] == "succeeded"
    assert run.json()["data"]["offers_received"] == 4

    offers = client.get(f"/api/v1/monitors/{monitor_id}/offers", headers=auth_headers)
    history = client.get(
        f"/api/v1/monitors/{monitor_id}/price-history",
        headers=auth_headers,
    )
    assert offers.status_code == 200
    assert offers.json()["data"]["total"] == 4
    assert history.json()["data"]["total"] == 4
    assert {item["source_name"] for item in offers.json()["data"]["items"]} == {"mock"}

    repeated = client.post(f"/api/v1/monitors/{monitor_id}/runs", headers=run_headers)
    assert repeated.json()["data"]["run_id"] == run_id
    history_after = client.get(
        f"/api/v1/monitors/{monitor_id}/price-history",
        headers=auth_headers,
    )
    assert history_after.json()["data"]["total"] == 4

    second_run = client.post(
        f"/api/v1/monitors/{monitor_id}/runs",
        headers={**auth_headers, "Idempotency-Key": "second-manual-run"},
    )
    assert second_run.status_code == 202
    paged_offers = client.get(
        f"/api/v1/monitors/{monitor_id}/offers?page=1&page_size=1",
        headers=auth_headers,
    ).json()["data"]
    paged_history = client.get(
        f"/api/v1/monitors/{monitor_id}/price-history?page=1&page_size=1",
        headers=auth_headers,
    ).json()["data"]
    assert len(paged_offers["items"]) == 1
    assert paged_offers["total"] == 4
    assert len(paged_history["items"]) == 1
    assert paged_history["total"] == 8

    alerts = client.get(
        f"/api/v1/alerts?monitor_id={monitor_id}",
        headers=auth_headers,
    ).json()["data"]
    assert alerts["total"] == 2
    assert {item["status"] for item in alerts["items"]} == {"sent", "suppressed"}
    sent = next(item for item in alerts["items"] if item["status"] == "sent")
    assert sent["rule_type"] == "price_below_limit"
    assert sent["provider"] == "fake"
    assert sent["attempt_count"] == 1
    assert "Brasília para Porto Velho" in sent["message"]

    repeated_dispatch = dispatch_alert_event(sent["id"])
    assert repeated_dispatch["status"] == "sent"
    with database.session() as session:
        persisted = session.get(AlertEvent, sent["id"])
        assert persisted is not None
        assert persisted.attempt_count == 1


def test_partial_source_failure_preserves_valid_results(
    client: TestClient,
    auth_headers: dict[str, str],
    monitor_payload: dict[str, object],
) -> None:
    payload = {
        **monitor_payload,
        "sources": ["mock", "mock-secondary"],
        "source_configuration": {"mock-secondary": {"mode": "error"}},
    }
    monitor_id = create_monitor(client, auth_headers, payload)
    response = client.post(
        f"/api/v1/monitors/{monitor_id}/runs",
        headers={**auth_headers, "Idempotency-Key": "partial-run"},
    )
    run_id = response.json()["data"]["run_id"]
    run = client.get(f"/api/v1/runs/{run_id}", headers=auth_headers).json()["data"]
    assert run["status"] == "partially_succeeded"
    assert run["sources_succeeded"] == 1
    assert run["sources_failed"] == 1
    offers = client.get(f"/api/v1/monitors/{monitor_id}/offers", headers=auth_headers).json()
    assert offers["data"]["total"] == 4


def test_new_historical_low_requires_a_previous_run(
    client: TestClient,
    auth_headers: dict[str, str],
    monitor_payload: dict[str, object],
) -> None:
    payload = {
        **monitor_payload,
        "source_configuration": {"mock": {"base_price_minor": 90000}},
        "alerts": {"new_historical_low": True},
    }
    monitor_id = create_monitor(client, auth_headers, payload)
    first = client.post(
        f"/api/v1/monitors/{monitor_id}/runs",
        headers={**auth_headers, "Idempotency-Key": "historical-baseline"},
    )
    assert first.status_code == 202
    baseline_alerts = client.get(
        f"/api/v1/alerts?monitor_id={monitor_id}", headers=auth_headers
    ).json()["data"]
    assert baseline_alerts["total"] == 0

    with database.session() as session:
        monitor_source = session.scalar(
            select(MonitorSource).where(MonitorSource.monitor_id == monitor_id)
        )
        assert monitor_source is not None
        monitor_source.configuration = {"schema_version": "1", "base_price_minor": 70000}
        session.commit()

    second = client.post(
        f"/api/v1/monitors/{monitor_id}/runs",
        headers={**auth_headers, "Idempotency-Key": "historical-lower-price"},
    )
    assert second.status_code == 202
    alerts = client.get(f"/api/v1/alerts?monitor_id={monitor_id}", headers=auth_headers).json()[
        "data"
    ]
    assert alerts["total"] == 1
    assert alerts["items"][0]["rule_type"] == "new_historical_low"
    assert alerts["items"][0]["status"] == "sent"
    assert "previous low" in alerts["items"][0]["message"]
