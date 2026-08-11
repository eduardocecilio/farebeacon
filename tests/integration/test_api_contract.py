from __future__ import annotations

from fastapi.testclient import TestClient


def test_authentication_error_uses_stable_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/monitors")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert response.json()["meta"]["request_id"].startswith("req_")


def test_monitor_creation_is_idempotent(
    client: TestClient,
    auth_headers: dict[str, str],
    monitor_payload: dict[str, object],
) -> None:
    headers = {**auth_headers, "Idempotency-Key": "create-bsb-pvh-monitor"}
    first = client.post("/api/v1/monitors", headers=headers, json=monitor_payload)
    second = client.post("/api/v1/monitors", headers=headers, json=monitor_payload)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["data"]["id"] == second.json()["data"]["id"]

    changed = {**monitor_payload, "name": "Different request"}
    conflict = client.post("/api/v1/monitors", headers=headers, json=changed)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_openapi_documents_security_and_idempotency(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert "BearerToken" in schema["components"]["securitySchemes"]
    operation = schema["paths"]["/api/v1/monitors"]["post"]
    assert any(parameter["name"] == "Idempotency-Key" for parameter in operation["parameters"])
