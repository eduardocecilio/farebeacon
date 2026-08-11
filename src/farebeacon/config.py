from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
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
    api_token: str = "development-only-token-change-me"
    database_url: str = "sqlite+pysqlite:///./farebeacon.db"
    redis_url: str = "redis://127.0.0.1:6379/0"
    artifacts_root: Path = Path(".artifacts")
    log_level: str = "INFO"
    celery_task_always_eager: bool = False
    default_source_timeout_seconds: int = Field(default=30, ge=1, le=300)

    @model_validator(mode="after")
    def reject_insecure_production_configuration(self) -> Settings:
        if self.env.lower() == "production":
            if len(self.api_token) < 32 or "change-me" in self.api_token:
                raise ValueError("production API token must be at least 32 characters")
            if self.database_url.startswith("sqlite"):
                raise ValueError("production must use PostgreSQL")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
