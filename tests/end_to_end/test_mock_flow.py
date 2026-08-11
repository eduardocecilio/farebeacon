from __future__ import annotations

from fastapi.testclient import TestClient


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
