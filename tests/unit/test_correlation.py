from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

from farebeacon.correlation import itinerary_hash
from farebeacon.domain.sources import NormalizedOffer, NormalizedSegment


def offer() -> NormalizedOffer:
    return NormalizedOffer(
        source_name="mock",
        source_offer_id="first",
        observed_at=datetime(2030, 1, 1, tzinfo=UTC),
        segments=(
            NormalizedSegment(
                leg_index=0,
                sequence=0,
                origin="BSB",
                destination="PVH",
                departure_at=datetime(2030, 7, 10, 11, tzinfo=UTC),
                arrival_at=datetime(2030, 7, 10, 14, tzinfo=UTC),
                marketing_airline="fb",
                operating_airline="FB",
                flight_number="FB 1234",
            ),
        ),
        total_price=Decimal("750.00"),
        currency="BRL",
        booking_url=None,
        baggage_summary=None,
        fare_brand=None,
        confidence_score=1.0,
        raw_payload={},
    )


def test_itinerary_hash_excludes_price_source_and_observation_time() -> None:
    first = offer()
    second = replace(
        first,
        source_name="mock-secondary",
        source_offer_id="second",
        total_price=Decimal("999.00"),
        observed_at=datetime(2030, 1, 2, tzinfo=UTC),
    )
    assert itinerary_hash(first) == itinerary_hash(second)


def test_itinerary_hash_changes_when_flight_changes() -> None:
    first = offer()
    changed_segment = replace(first.segments[0], flight_number="FB9999")
    assert itinerary_hash(first) != itinerary_hash(replace(first, segments=(changed_segment,)))
