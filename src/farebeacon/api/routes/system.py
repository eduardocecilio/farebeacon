from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError

from farebeacon.api.dependencies import get_database, get_settings
from farebeacon.api.responses import success
from farebeacon.api.schemas import ApiResponse, HealthRead, ReadyRead, VersionRead
from farebeacon.config import Settings
from farebeacon.infrastructure.db.session import Database

router = APIRouter(tags=["system"])


@router.get("/health", response_model=ApiResponse[HealthRead])
def health(request: Request, settings: Annotated[Settings, Depends(get_settings)]) -> object:
    return success(request, HealthRead(status="ok", version=settings.version))


@router.get(
    "/ready",
    response_model=ApiResponse[ReadyRead],
    responses={503: {"description": "A required dependency is unavailable"}},
)
def ready(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    database: Annotated[Database, Depends(get_database)],
) -> object:
    checks: dict[str, str] = {}
    try:
        database.healthcheck()
        checks["database"] = "ok"
    except SQLAlchemyError:
        checks["database"] = "unavailable"
    try:
        client = Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)
        checks["redis"] = "ok" if client.ping() else "unavailable"
        client.close()
    except RedisError:
        checks["redis"] = "unavailable"
    data = ReadyRead(
        status="ready" if set(checks.values()) == {"ok"} else "not_ready",
        checks=checks,
    )
    payload = success(request, data)
    if data.status != "ready":
        return JSONResponse(status_code=503, content=payload.model_dump(mode="json"))
    return payload


@router.get("/version", response_model=ApiResponse[VersionRead])
def version(request: Request, settings: Annotated[Settings, Depends(get_settings)]) -> object:
    return success(request, VersionRead(name="farebeacon", version=settings.version))
