from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

from farebeacon.domain.exceptions import SourceContractError
from farebeacon.domain.sources import (
    NormalizedOffer,
    NormalizedSegment,
    RawSourceItem,
    SearchQuery,
)


class MockSourceParser:
    version = "1.0.0"

    def __init__(self, *, source_name: str = "mock") -> None:
        self.source_name = source_name

    def normalize(
        self,
        item: RawSourceItem,
        *,
        query: SearchQuery,
        observed_at: datetime,
    ) -> Sequence[NormalizedOffer]:
        try:
            payload = item.payload
            segments = tuple(self._parse_segment(segment) for segment in payload["segments"])
            offer = NormalizedOffer(
                source_name=self.source_name,
                source_offer_id=item.source_offer_id,
                observed_at=observed_at,
                segments=segments,
                total_price=Decimal(str(payload["total_price"])),
                currency=str(payload["currency"]).upper(),
                booking_url=self._optional_string(payload.get("booking_url")),
                baggage_summary=self._optional_string(payload.get("baggage_summary")),
                fare_brand=self._optional_string(payload.get("fare_brand")),
                confidence_score=float(payload["confidence_score"]),
                raw_payload=dict(payload),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SourceContractError("MockSource returned an invalid payload") from exc
        return (offer,)

    @staticmethod
    def _parse_segment(payload: dict[str, Any]) -> NormalizedSegment:
        return NormalizedSegment(
            leg_index=int(payload["leg_index"]),
            sequence=int(payload["sequence"]),
            origin=str(payload["origin"]).upper(),
            destination=str(payload["destination"]).upper(),
            departure_at=datetime.fromisoformat(str(payload["departure_at"])),
            arrival_at=datetime.fromisoformat(str(payload["arrival_at"])),
            marketing_airline=MockSourceParser._optional_string(payload.get("marketing_airline")),
            operating_airline=MockSourceParser._optional_string(payload.get("operating_airline")),
            flight_number=MockSourceParser._optional_string(payload.get("flight_number")),
        )

    @staticmethod
    def _optional_string(value: object) -> str | None:
        return None if value is None else str(value)
