from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class NotificationMessage:
    event_id: str
    text: str


@dataclass(frozen=True, slots=True)
class DeliveryReceipt:
    provider_message_id: str | None = None


class NotificationDeliveryError(RuntimeError):
    """A provider rejected or could not deliver a notification."""


class Notifier(Protocol):
    name: str

    def send(self, message: NotificationMessage) -> DeliveryReceipt: ...
