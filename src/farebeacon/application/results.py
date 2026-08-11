from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from farebeacon.api.schemas import OfferRead, PriceHistoryRead, SegmentRead
from farebeacon.application.monitors import get_monitor
from farebeacon.infrastructure.db.models import (
    Itinerary,
    Quote,
    QuoteObservation,
    SearchRun,
)


def list_latest_offers(
    session: Session,
    *,
    monitor_id: str,
    page: int,
    page_size: int,
) -> tuple[list[OfferRead], int]:
    get_monitor(session, monitor_id)
    ranked = (
        select(
            QuoteObservation.id.label("observation_id"),
            QuoteObservation.observed_at.label("observed_at"),
            func.row_number()
            .over(
                partition_by=QuoteObservation.quote_id,
                order_by=(
                    QuoteObservation.observed_at.desc(),
                    QuoteObservation.created_at.desc(),
                    QuoteObservation.id.desc(),
                ),
            )
            .label("position"),
        )
        .join(SearchRun, SearchRun.id == QuoteObservation.search_run_id)
        .where(SearchRun.monitor_id == monitor_id)
        .subquery()
    )
    total = (
        session.scalar(select(func.count()).select_from(ranked).where(ranked.c.position == 1)) or 0
    )
    observations = list(
        session.scalars(
            select(QuoteObservation)
            .join(ranked, ranked.c.observation_id == QuoteObservation.id)
            .where(ranked.c.position == 1)
            .options(
                joinedload(QuoteObservation.quote)
                .joinedload(Quote.itinerary)
                .selectinload(Itinerary.segments),
                joinedload(QuoteObservation.source_run),
            )
            .order_by(ranked.c.observed_at.desc(), QuoteObservation.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .unique()
        .all()
    )
    return [_offer_to_read(item) for item in observations], total


def list_price_history(
    session: Session,
    *,
    monitor_id: str,
    page: int,
    page_size: int,
) -> tuple[list[PriceHistoryRead], int]:
    get_monitor(session, monitor_id)
    total = (
        session.scalar(
            select(func.count(QuoteObservation.id))
            .join(SearchRun, SearchRun.id == QuoteObservation.search_run_id)
            .where(SearchRun.monitor_id == monitor_id)
        )
        or 0
    )
    observations = list(
        session.scalars(
            select(QuoteObservation)
            .join(SearchRun, SearchRun.id == QuoteObservation.search_run_id)
            .where(SearchRun.monitor_id == monitor_id)
            .options(
                joinedload(QuoteObservation.quote),
                joinedload(QuoteObservation.source_run),
            )
            .order_by(QuoteObservation.observed_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return [
        PriceHistoryRead(
            observation_id=item.id,
            quote_id=item.quote_id,
            run_id=item.search_run_id,
            source_run_id=item.source_run_id,
            source_name=item.source_run.source_name,
            price_minor=item.price_minor,
            currency=item.currency,
            observed_at=item.observed_at,
        )
        for item in observations
    ], total


def _offer_to_read(observation: QuoteObservation) -> OfferRead:
    quote = observation.quote
    itinerary = quote.itinerary
    return OfferRead(
        quote_id=quote.id,
        itinerary_id=itinerary.id,
        itinerary_hash=itinerary.itinerary_hash,
        source_name=quote.source_name,
        source_offer_id=quote.source_offer_id,
        price_minor=observation.price_minor,
        currency=observation.currency,
        booking_url=quote.booking_url,
        baggage_summary=quote.baggage_summary,
        fare_brand=quote.fare_brand,
        confidence_score=float(quote.confidence_score),
        observed_at=observation.observed_at,
        stops=itinerary.stops,
        duration_minutes=itinerary.duration_minutes,
        segments=[
            SegmentRead(
                leg_index=segment.leg_index,
                sequence=segment.sequence,
                origin=segment.origin_iata,
                destination=segment.destination_iata,
                departure_at=segment.departure_at,
                arrival_at=segment.arrival_at,
                marketing_airline=segment.marketing_airline,
                operating_airline=segment.operating_airline,
                flight_number=segment.flight_number,
            )
            for segment in itinerary.segments
        ],
    )
