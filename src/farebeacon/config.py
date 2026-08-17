from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="FAREBEACON_",
        extra="ignore",
        case_sensitive=False,
    )

    env: str = "development"
    version: str = "0.1.0"
    api_token: SecretStr | None = None
    database_url: str = "sqlite+pysqlite:///./farebeacon.db"
    redis_url: str = "redis://127.0.0.1:6379/0"
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None
    artifacts_root: Path = Path(".artifacts")
    log_level: str = "INFO"
    celery_task_always_eager: bool = False
    demo_read_only: bool = False
    default_source_timeout_seconds: int = Field(default=30, ge=1, le=300)
    max_request_body_bytes: int = Field(default=1_048_576, ge=1024, le=10_485_760)
    max_source_payload_bytes: int = Field(default=4_194_304, ge=1024, le=52_428_800)
    default_alert_cooldown_minutes: int = Field(default=1440, ge=0, le=43_200)
    notification_backend: Literal["disabled", "fake", "telegram"] = "disabled"
    telegram_bot_token: SecretStr | None = None
    telegram_chat_id: str | None = None
    telegram_request_timeout_seconds: int = Field(default=10, ge=1, le=60)

    @model_validator(mode="after")
    def reject_insecure_production_configuration(self) -> Settings:
        if self.api_token is not None:
            token = self.api_token.get_secret_value()
            if len(token) < 32 or "change-me" in token.lower():
                raise ValueError("API token must be at least 32 characters and not a placeholder")
        if self.env.lower() == "production":
            if self.api_token is None:
                raise ValueError("production API token is required")
            if self.database_url.startswith("sqlite"):
                raise ValueError("production must use PostgreSQL")
            if self.notification_backend == "fake":
                raise ValueError("the fake notification backend cannot run in production")
        if self.notification_backend == "telegram":
            if (
                self.telegram_bot_token is None
                or not self.telegram_bot_token.get_secret_value().strip()
            ):
                raise ValueError("Telegram bot token is required for the telegram backend")
            if not self.telegram_chat_id or not self.telegram_chat_id.strip():
                raise ValueError("Telegram chat id is required for the telegram backend")
        return self

    @property
    def broker_url(self) -> str:
        """Celery broker. Redis is the default; a platform broker can replace it."""
        return self.celery_broker_url or self.redis_url

    @property
    def result_backend(self) -> str:
        """Celery result backend, which follows the broker unless it is overridden."""
        return self.celery_result_backend or self.redis_url

    @property
    def requires_redis(self) -> bool:
        """Redis is a runtime dependency only while it backs the broker or the results."""
        if self.celery_task_always_eager:
            return False
        return self.broker_url.startswith("redis") or self.result_backend.startswith("redis")

    def require_api_token(self) -> str:
        if self.api_token is None:
            raise ValueError("FAREBEACON_API_TOKEN is required by the HTTP API")
        return self.api_token.get_secret_value()

    def require_telegram_configuration(self) -> tuple[str, str]:
        token = (
            self.telegram_bot_token.get_secret_value().strip()
            if self.telegram_bot_token is not None
            else ""
        )
        if not token or not self.telegram_chat_id or not self.telegram_chat_id.strip():
            raise ValueError("Telegram notification configuration is incomplete")
        return token, self.telegram_chat_id.strip()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
