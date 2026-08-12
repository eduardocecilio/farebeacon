from __future__ import annotations

from farebeacon.domain.ports.notifications import (
    DeliveryReceipt,
    NotificationDeliveryError,
    NotificationMessage,
)


class FakeNotifier:
    name = "fake"

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.deliveries: list[NotificationMessage] = []

    def send(self, message: NotificationMessage) -> DeliveryReceipt:
        if self.fail:
            raise NotificationDeliveryError("Fake notification delivery failed")
        self.deliveries.append(message)
        return DeliveryReceipt(provider_message_id=f"fake:{message.event_id}")
