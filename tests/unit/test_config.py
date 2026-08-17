from __future__ import annotations

import pytest
from pydantic import ValidationError

from farebeacon.config import Settings


def test_http_api_requires_an_explicit_token() -> None:
    settings = Settings(api_token=None)
    with pytest.raises(ValueError, match="FAREBEACON_API_TOKEN"):
        settings.require_api_token()


def test_placeholder_token_is_rejected_in_every_environment() -> None:
    with pytest.raises(ValidationError, match="not a placeholder"):
        Settings(api_token="change-me-use-at-least-32-random-characters")


def test_token_is_redacted_from_settings_representation() -> None:
    token = "a-valid-test-token-with-at-least-thirty-two-characters"
    settings = Settings(api_token=token)
    assert token not in repr(settings)


def test_telegram_backend_requires_bot_token_and_chat_id() -> None:
    with pytest.raises(ValidationError, match="bot token"):
        Settings(notification_backend="telegram", telegram_chat_id="123456")
    with pytest.raises(ValidationError, match="bot token"):
        Settings(
            notification_backend="telegram",
            telegram_bot_token="   ",
            telegram_chat_id="123456",
        )
    with pytest.raises(ValidationError, match="chat id"):
        Settings(notification_backend="telegram", telegram_bot_token="telegram-secret")


def test_telegram_token_is_redacted_from_settings_representation() -> None:
    token = "telegram-token-that-must-stay-secret"
    settings = Settings(
        notification_backend="telegram",
        telegram_bot_token=token,
        telegram_chat_id="123456",
    )
    assert token not in repr(settings)


def test_broker_and_result_backend_default_to_redis() -> None:
    settings = Settings(redis_url="redis://cache:6379/2")
    assert settings.broker_url == "redis://cache:6379/2"
    assert settings.result_backend == "redis://cache:6379/2"
    assert settings.requires_redis is True


def test_a_platform_broker_replaces_redis() -> None:
    settings = Settings(
        celery_broker_url="vercel://",
        celery_result_backend="vercel-runtime-cache://",
    )
    assert settings.broker_url == "vercel://"
    assert settings.result_backend == "vercel-runtime-cache://"
    assert settings.requires_redis is False


def test_eager_execution_removes_the_redis_requirement() -> None:
    settings = Settings(celery_task_always_eager=True)
    assert settings.broker_url.startswith("redis")
    assert settings.requires_redis is False


def test_fake_notifications_are_rejected_in_production() -> None:
    with pytest.raises(ValidationError, match="fake notification backend"):
        Settings(
            env="production",
            api_token="a-valid-production-token-with-at-least-thirty-two-characters",
            database_url="postgresql+psycopg://farebeacon:secret@postgres/farebeacon",
            notification_backend="fake",
        )
