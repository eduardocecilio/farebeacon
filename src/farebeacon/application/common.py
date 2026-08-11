from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from farebeacon.api.errors import AppError
from farebeacon.domain.enums import SourceStatus
from farebeacon.infrastructure.db.models import IdempotencyRecord, SourceDefinition
from farebeacon.sources.registry import SourceRegistry


def request_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


def query_fingerprint(payload: dict[str, Any]) -> str:
    return request_digest(payload)


def idempotency_lookup(
    session: Session,
    *,
    scope: str,
    key: str,
    request_hash: str,
) -> IdempotencyRecord | None:
    record = session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.scope == scope,
            IdempotencyRecord.key == key,
        )
    )
    if record is not None and record.request_hash != request_hash:
        raise AppError(
            code="IDEMPOTENCY_CONFLICT",
            message="This Idempotency-Key was already used with a different request.",
            status_code=409,
            details={"scope": scope},
        )
    return record


def make_idempotency_record(
    *,
    scope: str,
    key: str,
    request_hash: str,
    resource_type: str,
    resource_id: str,
    response_status: int,
    response_body: dict[str, Any],
) -> IdempotencyRecord:
    return IdempotencyRecord(
        scope=scope,
        key=key,
        request_hash=request_hash,
        resource_type=resource_type,
        resource_id=resource_id,
        response_status=response_status,
        response_body=response_body,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )


def sync_source_definitions(session: Session, registry: SourceRegistry) -> None:
    for registered in registry.list():
        source = registered.source
        definition = session.get(SourceDefinition, source.name)
        capabilities = asdict(source.capabilities)
        if definition is None:
            session.add(
                SourceDefinition(
                    name=source.name,
                    kind=source.kind.value,
                    version=source.version,
                    is_enabled=True,
                    status=SourceStatus.HEALTHY.value,
                    capabilities=capabilities,
                    timeout_seconds=30,
                    max_concurrency=2,
                    cache_ttl_minutes=0,
                    parser_version=registered.parser.version,
                )
            )
        else:
            definition.kind = source.kind.value
            definition.version = source.version
            definition.capabilities = capabilities
            definition.parser_version = registered.parser.version


def parse_date(value: str | date) -> date:
    return value if isinstance(value, date) else date.fromisoformat(value)
