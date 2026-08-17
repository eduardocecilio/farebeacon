from __future__ import annotations

from farebeacon.config import Settings
from farebeacon.domain.ports.notifications import Notifier
from farebeacon.infrastructure.notifications.fake import FakeNotifier
from farebeacon.infrastructure.notifications.telegram import TelegramNotifier


def build_notifier(settings: Settings) -> Notifier | None:
    if settings.notification_backend == "disabled":
        return None
    if settings.notification_backend == "fake":
        return FakeNotifier()
    bot_token, chat_id = settings.require_telegram_configuration()
    return TelegramNotifier(
        bot_token=bot_token,
        chat_id=chat_id,
        timeout_seconds=settings.telegram_request_timeout_seconds,
    )


__all__ = ["FakeNotifier", "TelegramNotifier", "build_notifier"]
