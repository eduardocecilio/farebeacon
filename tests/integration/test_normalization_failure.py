from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from farebeacon.infrastructure.artifacts import LocalArtifactStore


def test_unexpected_normalization_failure_reaches_terminal_state(
    client: TestClient,
    auth_headers: dict[str, str],
    monitor_payload: dict[str, object],
    monkeypatch: Any,
) -> None:
    def fail_to_store(*args: Any, **kwargs: Any) -> None:
        raise OSError("simulated artifact storage failure")

    monkeypatch.setattr(LocalArtifactStore, "put", fail_to_store)
    monitor_response = client.post(
        "/api/v1/monitors",
        headers={**auth_headers, "Idempotency-Key": "normalization-failure-monitor"},
        json=monitor_payload,
    )
    monitor_id = monitor_response.json()["data"]["id"]

    run_response = client.post(
        f"/api/v1/monitors/{monitor_id}/runs",
        headers={**auth_headers, "Idempotency-Key": "normalization-failure-run"},
    )
    run_id = run_response.json()["data"]["run_id"]
    run = client.get(f"/api/v1/runs/{run_id}", headers=auth_headers).json()["data"]

    assert run["status"] == "failed"
    assert run["sources_failed"] == 1
    assert run["source_runs"][0]["status"] == "failed"
    assert run["source_runs"][0]["error_code"] == "INTERNAL_ERROR"
