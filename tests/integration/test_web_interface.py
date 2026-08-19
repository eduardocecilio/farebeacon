from __future__ import annotations

from fastapi.testclient import TestClient

from farebeacon.infrastructure.db.session import database
from farebeacon.scripts.seed_demo import seed


def test_the_index_lists_seeded_monitors(client: TestClient) -> None:
    with database.session() as session:
        monitor_ids = seed(session)

    response = client.get("/")
    assert response.status_code == 200
    assert "Airfare monitors" in response.text
    for monitor_id in monitor_ids:
        assert f"/monitors/{monitor_id}" in response.text


def test_a_monitor_page_shows_history_offers_and_alerts(client: TestClient) -> None:
    with database.session() as session:
        monitor_id = seed(session)[0]

    response = client.get(f"/monitors/{monitor_id}")
    assert response.status_code == 200
    assert "Price history" in response.text
    assert "Current offers" in response.text
    assert "Alert events" in response.text
    # Two runs with a price drop produce a trend, which is what the sparkline draws.
    assert "<polyline" in response.text


def test_the_price_history_fragment_renders_alone(client: TestClient) -> None:
    with database.session() as session:
        monitor_id = seed(session)[0]

    response = client.get(f"/monitors/{monitor_id}/price-history?page=1")
    assert response.status_code == 200
    assert response.text.lstrip().startswith("<section")
    assert "<html" not in response.text


def test_an_unknown_monitor_page_answers_the_documented_error(client: TestClient) -> None:
    response = client.get("/monitors/mon_does_not_exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "MONITOR_NOT_FOUND"
