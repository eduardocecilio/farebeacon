from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from farebeacon.api.dependencies import get_db, require_authentication
from farebeacon.api.errors import AppError
from farebeacon.api.responses import success
from farebeacon.api.schemas import COMMON_ERROR_RESPONSES, ApiResponse, PageData, SourceRead
from farebeacon.infrastructure.db.models import SourceDefinition
from farebeacon.sources.registry import RegisteredSource, get_source_registry

router = APIRouter(
    prefix="/api/v1/sources",
    tags=["sources"],
    dependencies=[Depends(require_authentication)],
    responses=COMMON_ERROR_RESPONSES,
)


@router.get("", response_model=ApiResponse[PageData[SourceRead]])
def get_sources(
    request: Request,
    session: Annotated[Session, Depends(get_db)],
) -> object:
    registered = get_source_registry().list()
    items = [_source_to_read(session, item, healthy=None) for item in registered]
    return success(request, PageData(items=items, page=1, page_size=len(items), total=len(items)))


@router.get("/{source_name}", response_model=ApiResponse[SourceRead])
def get_source(
    request: Request,
    source_name: str,
    session: Annotated[Session, Depends(get_db)],
) -> object:
    registered = _registered_source(source_name)
    return success(request, _source_to_read(session, registered, healthy=None))


@router.get("/{source_name}/health", response_model=ApiResponse[SourceRead])
async def get_source_health(
    request: Request,
    source_name: str,
    session: Annotated[Session, Depends(get_db)],
) -> object:
    registered = _registered_source(source_name)
    healthy = await registered.source.healthcheck()
    return success(request, _source_to_read(session, registered, healthy=healthy))


def _registered_source(source_name: str) -> RegisteredSource:
    try:
        return get_source_registry().get(source_name)
    except KeyError as exc:
        raise AppError(
            code="SOURCE_NOT_FOUND",
            message="Source not found.",
            status_code=404,
            details={"source": source_name},
        ) from exc


def _source_to_read(
    session: Session,
    registered: RegisteredSource,
    *,
    healthy: bool | None,
) -> SourceRead:
    definition = session.get(SourceDefinition, registered.source.name)
    return SourceRead(
        name=registered.source.name,
        kind=registered.source.kind.value,
        version=registered.source.version,
        parser_version=registered.parser.version,
        enabled=definition.is_enabled if definition else True,
        healthy=healthy,
        capabilities=asdict(registered.source.capabilities),
    )
