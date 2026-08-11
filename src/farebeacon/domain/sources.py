from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Protocol

from farebeacon.domain.enums import SourceKind

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]


def _validate_iata(value: str) -> str:
    normalized = value.strip().upper()
    if len(normalized) != 3 or not normalized.isascii() or not normalized.isalpha():
        raise ValueError(f"invalid IATA location code: {value!r}")
    return normalized


@dataclass(frozen=True, slots=True)
class SourceCapabilities:
    supports_one_way: bool = True
    supports_round_trip: bool = True
    supports_multiple_passengers: bool = True
    supports_cabin_class: bool = True
    supports_direct_filter: bool = False
    supports_booking_url: bool = False
    supports_baggage: bool = False


@dataclass(frozen=True, slots=True)
class SearchQuery:
    origin: str
    destination: str
    departure_date: date
    return_date: date | None
    adults: int
    children: int
    infants: int
    cabin_class: str
    currency: str
    max_stops: int | None
    locale: str = "pt-BR"
    market: str = "BR"

    def __post_init__(self) -> None:
        object.__setattr__(self, "origin", _validate_iata(self.origin))
        object.__setattr__(self, "destination", _validate_iata(self.destination))
        object.__setattr__(self, "currency", self.currency.strip().upper())
        if self.origin == self.destination:
            raise ValueError("origin and destination must differ")
        if self.adults < 1 or min(self.children, self.infants) < 0:
            raise ValueError("passenger counts are invalid")
        if self.return_date is not None and self.return_date <= self.departure_date:
            raise ValueError("return_date must be after departure_date")
        if self.max_stops is not None and self.max_stops < 0:
            raise ValueError("max_stops cannot be negative")


@dataclass(frozen=True, slots=True)
class SourceExecutionContext:
    run_id: str
    source_run_id: str
    timeout_seconds: int
    correlation_id: str
    configuration: Mapping[str, JsonValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RawSourceItem:
    source_offer_id: str | None
    payload: dict[str, Any] = field(repr=False)


@dataclass(frozen=True, slots=True)
class SourceBatch:
    source_name: str
    query: SearchQuery
    observed_at: datetime
    items: tuple[RawSourceItem, ...]
    quota_cost: int = 0
    http_status: int | None = None
    parser_version: str | None = None


@dataclass(frozen=True, slots=True)
class NormalizedSegment:
    leg_index: int
    sequence: int
    origin: str
    destination: str
    departure_at: datetime
    arrival_at: datetime
    marketing_airline: str | None
    operating_airline: str | None
    flight_number: str | None


@dataclass(frozen=True, slots=True)
class NormalizedOffer:
    source_name: str
    source_offer_id: str | None
    observed_at: datetime
    segments: tuple[NormalizedSegment, ...]
    total_price: Decimal
    currency: str
    booking_url: str | None
    baggage_summary: str | None
    fare_brand: str | None
    confidence_score: float
    raw_payload: dict[str, Any] = field(repr=False)


class SearchSource(Protocol):
    name: str
    kind: SourceKind
    version: str
    capabilities: SourceCapabilities

    async def healthcheck(self) -> bool: ...

    async def estimate_cost(self, query: SearchQuery) -> int: ...

    async def fetch(
        self,
        query: SearchQuery,
        context: SourceExecutionContext,
    ) -> SourceBatch: ...


class SourceParser(Protocol):
    source_name: str
    version: str

    def normalize(
        self,
        item: RawSourceItem,
        *,
        query: SearchQuery,
        observed_at: datetime,
    ) -> Sequence[NormalizedOffer]: ...
