from __future__ import annotations

import json

import httpx
import pytest

from farebeacon.domain.ports.notifications import NotificationDeliveryError, NotificationMessage
from farebeacon.infrastructure.notifications import FakeNotifier, TelegramNotifier


def test_fake_notifier_records_a_deterministic_delivery() -> None:
    notifier = FakeNotifier()
    message = NotificationMessage(event_id="alert_123", text="A lower fare was found.")

    receipt = notifier.send(message)

    assert notifier.deliveries == [message]
    assert receipt.provider_message_id == "fake:alert_123"


def test_telegram_notifier_sends_plain_text_and_returns_message_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/botsecret-token/sendMessage"
        assert request.headers["content-type"] == "application/json"
        assert json.loads(request.content) == {
            "chat_id": "123456",
            "text": "Fare found",
            "link_preview_options": {"is_disabled": True},
        }
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 42}})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        notifier = TelegramNotifier(
            bot_token="secret-token",
            chat_id="123456",
            client=client,
        )
        receipt = notifier.send(NotificationMessage(event_id="alert_123", text="Fare found"))

    assert receipt.provider_message_id == "42"


def test_telegram_notifier_sanitizes_provider_failures() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"ok": False, "description": "Unauthorized"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        notifier = TelegramNotifier(
            bot_token="must-not-appear",
            chat_id="123456",
            client=client,
        )
        with pytest.raises(NotificationDeliveryError) as raised:
            notifier.send(NotificationMessage(event_id="alert_123", text="Fare found"))

    assert "HTTP 401" in str(raised.value)
    assert "must-not-appear" not in str(raised.value)
