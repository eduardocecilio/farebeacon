from __future__ import annotations

import secrets
from collections.abc import Iterator
from typing import Annotated, cast

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from farebeacon.api.errors import AppError
from farebeacon.config import Settings
from farebeacon.infrastructure.db.session import Database

bearer_scheme = HTTPBearer(auto_error=False, scheme_name="BearerToken")


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def get_database(request: Request) -> Database:
    return cast(Database, request.app.state.database)


def get_db(database: Annotated[Database, Depends(get_database)]) -> Iterator[Session]:
    with database.session() as session:
        yield session


READ_ONLY_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def require_authentication(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    if settings.demo_read_only and request.method in READ_ONLY_METHODS:
        return
    configured_token = settings.require_api_token()
    valid = (
        credentials is not None
        and credentials.scheme.lower() == "bearer"
        and secrets.compare_digest(credentials.credentials, configured_token)
    )
    if not valid:
        raise AppError(
            code="AUTHENTICATION_REQUIRED",
            message="A valid Bearer token is required.",
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_idempotency_key(
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", min_length=8, max_length=255),
    ] = None,
) -> str:
    if idempotency_key is None:
        raise AppError(
            code="VALIDATION_ERROR",
            message="Idempotency-Key header is required for this operation.",
            status_code=400,
            details={"header": "Idempotency-Key"},
        )
    return idempotency_key


def pagination(
    page: int = 1,
    page_size: int = 20,
) -> tuple[int, int]:
    if page < 1 or not 1 <= page_size <= 100:
        raise AppError(
            code="VALIDATION_ERROR",
            message="Invalid pagination parameters.",
            status_code=422,
            details={"page": page, "page_size": page_size},
        )
    return page, page_size
