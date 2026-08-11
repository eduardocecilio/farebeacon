from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime, time, timedelta
from typing import Any

from farebeacon.domain.enums import SourceKind
from farebeacon.domain.exceptions import SourceExecutionError, SourceTimeoutError
from farebeacon.domain.money import minor_to_decimal
from farebeacon.domain.sources import (
    RawSourceItem,
    SearchQuery,
    SourceBatch,
    SourceCapabilities,
    SourceExecutionContext,
)


class MockSource:
    kind = SourceKind.MOCK
    version = "1.0.0"
    capabilities = SourceCapabilities(
        supports_direct_filter=True,
        supports_booking_url=False,
        supports_baggage=True,
    )

    def __init__(self, *, name: str = "mock") -> None:
        self.name = name

    async def healthcheck(self) -> bool:
        return True

    async def estimate_cost(self, query: SearchQuery) -> int:
        return 0

    async def fetch(
        self,
        query: SearchQuery,
        context: SourceExecutionContext,
    ) -> SourceBatch:
        mode = str(context.configuration.get("mode", "success"))
        if mode == "error":
            raise SourceExecutionError("MockSource configured to simulate a transient failure")
        if mode == "timeout":
            await asyncio.sleep(0)
            raise SourceTimeoutError("MockSource configured to simulate a timeout")

        observed_at = datetime.now(UTC)
        if mode == "empty":
            return SourceBatch(
                source_name=self.name,
                query=query,
                observed_at=observed_at,
                items=(),
                parser_version="1.0.0",
            )

        configured_price = context.configuration.get("base_price_minor", 73000)
        if isinstance(configured_price, bool) or not isinstance(configured_price, (str, int)):
            raise SourceExecutionError("MockSource base_price_minor must be an integer")
        base_price_minor = int(configured_price)
        if base_price_minor <= 0:
            raise SourceExecutionError("MockSource base_price_minor must be positive")
        seed = int(
            hashlib.sha256(
                f"{self.name}:{query.origin}:{query.destination}:{query.departure_date}".encode()
            ).hexdigest()[:8],
            16,
        )
        variation = seed % 12000
        passenger_factor = query.adults + query.children
        direct_price = base_price_minor + variation + max(passenger_factor - 1, 0) * 35000
        items = [self._offer(query, direct_price, connected=False)]
        if query.max_stops is None or query.max_stops >= 1:
            items.append(self._offer(query, direct_price - 8500, connected=True))
        if bool(context.configuration.get("duplicate_first", False)):
            items.append(items[0])

        return SourceBatch(
            source_name=self.name,
            query=query,
            observed_at=observed_at,
            items=tuple(items),
            quota_cost=0,
            parser_version="1.0.0",
        )

    def _offer(self, query: SearchQuery, price_minor: int, *, connected: bool) -> RawSourceItem:
        style = "connection" if connected else "direct"
        identity = (
            f"{self.name}:{query.origin}:{query.destination}:"
            f"{query.departure_date}:{query.return_date}:{style}"
        )
        offer_id = f"mock_{hashlib.sha256(identity.encode()).hexdigest()[:20]}"
        segments = self._leg_segments(
            origin=query.origin,
            destination=query.destination,
            travel_date=query.departure_date,
            leg_index=0,
            connected=connected,
            seed=identity,
        )
        if query.return_date is not None:
            segments.extend(
                self._leg_segments(
                    origin=query.destination,
                    destination=query.origin,
                    travel_date=query.return_date,
                    leg_index=1,
                    connected=connected,
                    seed=f"{identity}:return",
                )
            )
            price_minor *= 2
        return RawSourceItem(
            source_offer_id=offer_id,
            payload={
                "source_name": self.name,
                "source_offer_id": offer_id,
                "segments": segments,
                "total_price": str(minor_to_decimal(price_minor, query.currency)),
                "currency": query.currency,
                "booking_url": None,
                "baggage_summary": "1 personal item",
                "fare_brand": "Mock Economy",
                "confidence_score": 1.0,
            },
        )

    @staticmethod
    def _connection_airport(origin: str, destination: str) -> str:
        for candidate in ("CGB", "GRU", "CNF"):
            if candidate not in {origin, destination}:
                return candidate
        return "GIG"

    def _leg_segments(
        self,
        *,
        origin: str,
        destination: str,
        travel_date: Any,
        leg_index: int,
        connected: bool,
        seed: str,
    ) -> list[dict[str, Any]]:
        departure = datetime.combine(travel_date, time(11, 0), tzinfo=UTC)
        number_seed = int(hashlib.sha256(seed.encode()).hexdigest()[:4], 16)
        if not connected:
            return [
                self._segment(
                    leg_index=leg_index,
                    sequence=0,
                    origin=origin,
                    destination=destination,
                    departure=departure,
                    arrival=departure + timedelta(hours=2, minutes=45),
                    flight_number=f"FB{1000 + number_seed % 8000}",
                )
            ]

        connection = self._connection_airport(origin, destination)
        first_arrival = departure + timedelta(hours=1, minutes=35)
        second_departure = first_arrival + timedelta(hours=1, minutes=10)
        return [
            self._segment(
                leg_index=leg_index,
                sequence=0,
                origin=origin,
                destination=connection,
                departure=departure,
                arrival=first_arrival,
                flight_number=f"FB{1000 + number_seed % 4000}",
            ),
            self._segment(
                leg_index=leg_index,
                sequence=1,
                origin=connection,
                destination=destination,
                departure=second_departure,
                arrival=second_departure + timedelta(hours=2),
                flight_number=f"FB{5000 + number_seed % 4000}",
            ),
        ]

    @staticmethod
    def _segment(
        *,
        leg_index: int,
        sequence: int,
        origin: str,
        destination: str,
        departure: datetime,
        arrival: datetime,
        flight_number: str,
    ) -> dict[str, Any]:
        return {
            "leg_index": leg_index,
            "sequence": sequence,
            "origin": origin,
            "destination": destination,
            "departure_at": departure.isoformat(),
            "arrival_at": arrival.isoformat(),
            "marketing_airline": "FB",
            "operating_airline": "FB",
            "flight_number": flight_number,
        }
