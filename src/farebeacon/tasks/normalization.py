from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from farebeacon.config import get_settings
from farebeacon.correlation import itinerary_hash, quote_fingerprint
from farebeacon.domain.enums import RunStatus, SourceRunStatus, SourceStatus
from farebeacon.domain.exceptions import DomainError
from farebeacon.domain.money import decimal_to_minor
from farebeacon.domain.sources import NormalizedOffer
from farebeacon.domain.validation import validate_offer
from farebeacon.infrastructure.artifacts import LocalArtifactStore
from farebeacon.infrastructure.db.models import (
    FlightSegment,
    Itinerary,
    Quote,
    QuoteObservation,
    RawArtifact,
    SearchRun,
    SourceDefinition,
    SourceRun,
)
from farebeacon.infrastructure.db.session import database
from farebeacon.sources.registry import get_source_registry
from farebeacon.tasks.celery_app import celery_app
from farebeacon.tasks.serialization import deserialize_batch

TERMINAL_SOURCE_STATUSES = {
    SourceRunStatus.SUCCEEDED.value,
    SourceRunStatus.FAILED.value,
    SourceRunStatus.CANCELLED.value,
}
TERMINAL_RUN_STATUSES = {
    RunStatus.SUCCEEDED.value,
    RunStatus.PARTIALLY_SUCCEEDED.value,
    RunStatus.FAILED.value,
    RunStatus.CANCELLED.value,
}


@celery_app.task(name="farebeacon.normalize_source_results")  # type: ignore[untyped-decorator]
def normalize_source_results(source_result: dict[str, Any], source_run_id: str) -> dict[str, Any]:
    try:
        return _normalize_source_results(source_result, source_run_id)
    except Exception:
        logging.getLogger("farebeacon.normalization").exception(
            "normalization task failed unexpectedly",
            extra={"source_run_id": source_run_id},
        )
        try:
            _mark_normalization_failed(source_run_id)
        except Exception:
            logging.getLogger("farebeacon.normalization").exception(
                "normalization failure could not be persisted",
                extra={"source_run_id": source_run_id},
            )
        return {"source_run_id": source_run_id, "status": SourceRunStatus.FAILED.value}


def _normalize_source_results(
    source_result: dict[str, Any],
    source_run_id: str,
) -> dict[str, Any]:
    with database.session() as session:
        source_run = session.scalar(
            select(SourceRun)
            .where(SourceRun.id == source_run_id)
            .options(joinedload(SourceRun.search_run))
        )
        if source_run is None:
            return {"source_run_id": source_run_id, "status": "missing"}
        if source_run.status in TERMINAL_SOURCE_STATUSES:
            finalize_search_run(session, source_run.search_run_id)
            return {"source_run_id": source_run_id, "status": source_run.status}

        if source_result.get("status") == "failed":
            error = source_result.get("error", {})
            source_run.status = SourceRunStatus.FAILED.value
            source_run.error_code = str(error.get("code", "SOURCE_TEMPORARILY_UNAVAILABLE"))
            source_run.error_message = str(error.get("message", "Source execution failed."))[:2000]
            source_run.finished_at = datetime.now(UTC)
            definition = session.get(SourceDefinition, source_run.source_name)
            if definition is not None:
                definition.status = SourceStatus.DEGRADED.value
                definition.last_failure_at = datetime.now(UTC)
            session.commit()
            finalize_search_run(session, source_run.search_run_id)
            return {"source_run_id": source_run_id, "status": source_run.status}

        artifact = _persist_artifact(session, source_run, source_result)
        registered = get_source_registry().get(source_run.source_name)
        persisted = 0
        invalid_errors: list[str] = []
        for batch_payload in source_result.get("batches", []):
            batch = deserialize_batch(batch_payload)
            source_run.quota_cost += batch.quota_cost
            source_run.http_status = batch.http_status
            source_run.parser_version = batch.parser_version or registered.parser.version
            for item in batch.items:
                try:
                    offers = registered.parser.normalize(
                        item,
                        query=batch.query,
                        observed_at=batch.observed_at,
                    )
                    for offer in offers:
                        validate_offer(offer, batch.query)
                        if _persist_offer(session, source_run, offer, artifact):
                            persisted += 1
                except DomainError as error:
                    invalid_errors.append(str(error))

        source_run.status = SourceRunStatus.SUCCEEDED.value
        source_run.finished_at = datetime.now(UTC)
        if invalid_errors and persisted == 0:
            source_run.status = SourceRunStatus.FAILED.value
            source_run.error_code = "NO_VALID_OFFERS"
            source_run.error_message = invalid_errors[0][:2000]
        definition = session.get(SourceDefinition, source_run.source_name)
        if definition is not None:
            if source_run.status == SourceRunStatus.SUCCEEDED.value:
                definition.status = SourceStatus.HEALTHY.value
                definition.last_success_at = datetime.now(UTC)
            else:
                definition.status = SourceStatus.DEGRADED.value
                definition.last_failure_at = datetime.now(UTC)
        session.commit()
        finalize_search_run(session, source_run.search_run_id)
        return {
            "source_run_id": source_run_id,
            "status": source_run.status,
            "persisted": persisted,
        }


def _mark_normalization_failed(source_run_id: str) -> None:
    with database.session() as session:
        source_run = session.scalar(
            select(SourceRun)
            .where(SourceRun.id == source_run_id)
            .options(joinedload(SourceRun.search_run))
        )
        if source_run is None:
            return
        if source_run.status in TERMINAL_SOURCE_STATUSES:
            finalize_search_run(session, source_run.search_run_id)
            return
        source_run.status = SourceRunStatus.FAILED.value
        source_run.error_code = "INTERNAL_ERROR"
        source_run.error_message = "Normalization failed unexpectedly."
        source_run.finished_at = datetime.now(UTC)
        definition = session.get(SourceDefinition, source_run.source_name)
        if definition is not None:
            definition.status = SourceStatus.DEGRADED.value
            definition.last_failure_at = datetime.now(UTC)
        session.commit()
        finalize_search_run(session, source_run.search_run_id)


def _persist_artifact(
    session: Session,
    source_run: SourceRun,
    source_result: dict[str, Any],
) -> RawArtifact:
    key = f"raw/{source_run.search_run_id}/{source_run.id}.json"
    existing = session.scalar(select(RawArtifact).where(RawArtifact.storage_key == key))
    if existing is not None:
        return existing
    content = json.dumps(source_result, sort_keys=True, separators=(",", ":")).encode()
    stored = LocalArtifactStore(get_settings().artifacts_root).put(
        storage_key=key,
        content=content,
        content_type="application/json",
    )
    artifact = RawArtifact(
        artifact_type="json",
        storage_backend="local",
        storage_key=stored.storage_key,
        content_type=stored.content_type,
        sha256=stored.sha256,
        size_bytes=stored.size_bytes,
        is_sanitized=False,
    )
    session.add(artifact)
    session.flush()
    return artifact


def _persist_offer(
    session: Session,
    source_run: SourceRun,
    offer: NormalizedOffer,
    artifact: RawArtifact,
) -> bool:
    digest = itinerary_hash(offer)
    itinerary = session.scalar(select(Itinerary).where(Itinerary.itinerary_hash == digest))
    if itinerary is None:
        itinerary = _create_itinerary(offer, digest)
        try:
            with session.begin_nested():
                session.add(itinerary)
                session.flush()
        except IntegrityError:
            itinerary = session.scalar(select(Itinerary).where(Itinerary.itinerary_hash == digest))
            if itinerary is None:
                raise

    fingerprint = quote_fingerprint(offer, digest)
    quote = session.scalar(select(Quote).where(Quote.quote_fingerprint == fingerprint))
    price_minor = decimal_to_minor(offer.total_price, offer.currency)
    if quote is None:
        quote = Quote(
            itinerary_id=itinerary.id,
            source_name=offer.source_name,
            source_offer_id=offer.source_offer_id,
            quote_fingerprint=fingerprint,
            price_minor=price_minor,
            currency=offer.currency,
            booking_url=offer.booking_url,
            baggage_summary=offer.baggage_summary,
            fare_brand=offer.fare_brand,
            confidence_score=Decimal(str(offer.confidence_score)),
        )
        try:
            with session.begin_nested():
                session.add(quote)
                session.flush()
        except IntegrityError:
            quote = session.scalar(select(Quote).where(Quote.quote_fingerprint == fingerprint))
            if quote is None:
                raise
    else:
        quote.price_minor = price_minor
        quote.currency = offer.currency
        quote.booking_url = offer.booking_url
        quote.baggage_summary = offer.baggage_summary
        quote.fare_brand = offer.fare_brand
        quote.confidence_score = Decimal(str(offer.confidence_score))

    existing_observation = session.scalar(
        select(QuoteObservation).where(
            QuoteObservation.quote_id == quote.id,
            QuoteObservation.source_run_id == source_run.id,
        )
    )
    if existing_observation is not None:
        return False
    session.add(
        QuoteObservation(
            quote_id=quote.id,
            search_run_id=source_run.search_run_id,
            source_run_id=source_run.id,
            price_minor=price_minor,
            currency=offer.currency,
            observed_at=offer.observed_at,
            raw_artifact_id=artifact.id,
        )
    )
    session.flush()
    return True


def _create_itinerary(offer: NormalizedOffer, digest: str) -> Itinerary:
    ordered = sorted(offer.segments, key=lambda item: (item.leg_index, item.sequence))
    outbound = [segment for segment in ordered if segment.leg_index == 0]
    duration = sum(
        int((segment.arrival_at - segment.departure_at).total_seconds() // 60)
        for segment in ordered
    )
    itinerary = Itinerary(
        itinerary_hash=digest,
        origin_iata=outbound[0].origin,
        destination_iata=outbound[-1].destination,
        departure_at=outbound[0].departure_at,
        arrival_at=outbound[-1].arrival_at,
        duration_minutes=duration,
        stops=len(outbound) - 1,
    )
    for segment in ordered:
        itinerary.segments.append(
            FlightSegment(
                leg_index=segment.leg_index,
                sequence=segment.sequence,
                origin_iata=segment.origin,
                destination_iata=segment.destination,
                departure_at=segment.departure_at,
                arrival_at=segment.arrival_at,
                marketing_airline=segment.marketing_airline,
                operating_airline=segment.operating_airline,
                flight_number=segment.flight_number,
            )
        )
    return itinerary


def finalize_search_run(session: Session, run_id: str) -> None:
    run = session.get(SearchRun, run_id)
    if run is None or run.status in TERMINAL_RUN_STATUSES:
        return
    source_runs = list(session.scalars(select(SourceRun).where(SourceRun.search_run_id == run_id)))
    if not source_runs or any(item.status not in TERMINAL_SOURCE_STATUSES for item in source_runs):
        return
    succeeded = sum(item.status == SourceRunStatus.SUCCEEDED.value for item in source_runs)
    failed = sum(item.status == SourceRunStatus.FAILED.value for item in source_runs)
    offers = (
        session.scalar(
            select(func.count())
            .select_from(QuoteObservation)
            .where(QuoteObservation.search_run_id == run_id)
        )
        or 0
    )
    run.sources_requested = len(source_runs)
    run.sources_succeeded = succeeded
    run.sources_failed = failed
    run.offers_received = offers
    run.finished_at = datetime.now(UTC)
    errors = [
        {
            "source": item.source_name,
            "code": item.error_code,
            "message": item.error_message,
        }
        for item in source_runs
        if item.status == SourceRunStatus.FAILED.value
    ]
    run.error_summary = {"sources": errors} if errors else None
    if offers == 0:
        run.status = RunStatus.FAILED.value
        run.error_summary = run.error_summary or {
            "code": "NO_VALID_OFFERS",
            "message": "No source produced a valid offer.",
        }
    elif failed:
        run.status = RunStatus.PARTIALLY_SUCCEEDED.value
    else:
        run.status = RunStatus.SUCCEEDED.value
    from farebeacon.application.alerts import evaluate_alerts_for_run

    pending_event_ids = evaluate_alerts_for_run(
        session,
        run_id=run.id,
        default_cooldown_minutes=get_settings().default_alert_cooldown_minutes,
    )
    session.commit()
    if pending_event_ids:
        from farebeacon.tasks.alerts import queue_alert_events

        queue_alert_events(pending_event_ids)
