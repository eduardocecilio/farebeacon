from __future__ import annotations

import httpx

from farebeacon.domain.ports.notifications import (
    DeliveryReceipt,
    NotificationDeliveryError,
    NotificationMessage,
)


class TelegramNotifier:
    name = "telegram"

    def __init__(
        self,
        *,
        bot_token: str,
        chat_id: str,
        timeout_seconds: int = 10,
        client: httpx.Client | None = None,
    ) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._timeout_seconds = timeout_seconds
        self._client = client

    def send(self, message: NotificationMessage) -> DeliveryReceipt:
        endpoint = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
        payload = {
            "chat_id": self._chat_id,
            "text": message.text,
            "link_preview_options": {"is_disabled": True},
        }
        try:
            if self._client is not None:
                response = self._client.post(endpoint, json=payload)
            else:
                with httpx.Client(timeout=self._timeout_seconds) as client:
                    response = client.post(endpoint, json=payload)
        except httpx.HTTPError as exc:
            raise NotificationDeliveryError("Telegram request failed") from exc

        if response.status_code != 200:
            raise NotificationDeliveryError(f"Telegram returned HTTP {response.status_code}")
        try:
            body = response.json()
            message_id = body["result"]["message_id"] if body.get("ok") is True else None
        except (KeyError, TypeError, ValueError) as exc:
            raise NotificationDeliveryError("Telegram returned an invalid response") from exc
        if message_id is None:
            raise NotificationDeliveryError("Telegram rejected the message")
        return DeliveryReceipt(provider_message_id=str(message_id))
