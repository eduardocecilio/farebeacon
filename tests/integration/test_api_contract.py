from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient


def test_the_root_serves_the_interface_without_a_token(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "FareBeacon" in response.text


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
    assert "ErrorResponse" in schema["components"]["schemas"]
    assert operation["responses"]["422"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorResponse"
    }


def test_monitor_configuration_is_strict_and_request_size_is_bounded(
    client: TestClient,
    auth_headers: dict[str, str],
    monitor_payload: dict[str, object],
) -> None:
    invalid_configuration = {
        **monitor_payload,
        "source_configuration": {"mock": {"unknown_option": "not allowed"}},
    }
    response = client.post(
        "/api/v1/monitors",
        headers={**auth_headers, "Idempotency-Key": "strict-source-configuration"},
        json=invalid_configuration,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    oversized = client.post(
        "/api/v1/monitors",
        headers={**auth_headers, "Idempotency-Key": "oversized-request-body"},
        json={"padding": "x" * 1_048_576},
    )
    assert oversized.status_code == 413
    assert oversized.json()["error"]["code"] == "VALIDATION_ERROR"

    def streamed_body() -> Iterator[bytes]:
        yield b'{"padding":"'
        yield b"x" * 1_048_576
        yield b'"}'

    chunked = client.post(
        "/api/v1/monitors",
        headers={
            **auth_headers,
            "Idempotency-Key": "chunked-oversized-request",
        },
        content=streamed_body(),
    )
    assert chunked.status_code == 413
    assert chunked.json()["error"]["code"] == "VALIDATION_ERROR"
