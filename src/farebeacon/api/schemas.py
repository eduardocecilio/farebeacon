from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ResponseMeta(StrictModel):
    request_id: str


class ApiResponse[T](StrictModel):
    data: T
    meta: ResponseMeta


class PageData[T](StrictModel):
    items: list[T]
    page: int
    page_size: int
    total: int


type ErrorCode = Literal[
    "VALIDATION_ERROR",
    "AUTHENTICATION_REQUIRED",
    "MONITOR_NOT_FOUND",
    "RUN_NOT_FOUND",
    "RUN_ALREADY_ACTIVE",
    "ALERT_NOT_FOUND",
    "SOURCE_NOT_FOUND",
    "SOURCE_DISABLED",
    "SOURCE_RATE_LIMITED",
    "SOURCE_QUOTA_EXCEEDED",
    "SOURCE_TEMPORARILY_UNAVAILABLE",
    "SOURCE_CONTRACT_CHANGED",
    "NO_VALID_OFFERS",
    "IDEMPOTENCY_CONFLICT",
    "INTERNAL_ERROR",
]


class ErrorBody(StrictModel):
    code: ErrorCode
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(StrictModel):
    error: ErrorBody
    meta: ResponseMeta


def _error_response(description: str, code: ErrorCode) -> dict[str, Any]:
    return {
        "model": ErrorResponse,
        "description": description,
        "headers": {
            "X-Request-ID": {
                "description": "Stable request correlation identifier.",
                "schema": {"type": "string"},
            }
        },
        "content": {
            "application/json": {
                "example": {
                    "error": {
                        "code": code,
                        "message": description,
                        "details": {},
                    },
                    "meta": {"request_id": "req_01JEXAMPLE0000000000000000"},
                }
            }
        },
    }


COMMON_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: _error_response("The request is invalid.", "VALIDATION_ERROR"),
    401: _error_response("Authentication is required.", "AUTHENTICATION_REQUIRED"),
    404: _error_response("The requested resource was not found.", "MONITOR_NOT_FOUND"),
    409: _error_response("The request conflicts with current state.", "IDEMPOTENCY_CONFLICT"),
    413: _error_response("The request body is too large.", "VALIDATION_ERROR"),
    422: _error_response("The request payload is invalid.", "VALIDATION_ERROR"),
    500: _error_response("An unexpected internal error occurred.", "INTERNAL_ERROR"),
}


class RouteInput(StrictModel):
    origin: str = Field(min_length=3, max_length=3, examples=["BSB"])
    destination: str = Field(min_length=3, max_length=3, examples=["PVH"])

    @model_validator(mode="after")
    def validate_route(self) -> RouteInput:
        self.origin = self.origin.upper()
        self.destination = self.destination.upper()
        if not re.fullmatch(r"[A-Z]{3}", self.origin):
            raise ValueError("origin must be a three-letter IATA location code")
        if not re.fullmatch(r"[A-Z]{3}", self.destination):
            raise ValueError("destination must be a three-letter IATA location code")
        if self.origin == self.destination:
            raise ValueError("origin and destination must differ")
        return self


class PassengersInput(StrictModel):
    adults: int = Field(default=1, ge=1, le=9)
    children: int = Field(default=0, ge=0, le=9)
    infants: int = Field(default=0, ge=0, le=9)


class FiltersInput(StrictModel):
    currency: str = Field(default="BRL", min_length=3, max_length=3)
    cabin_class: str = Field(default="economy", min_length=2, max_length=30)
    max_stops: int | None = Field(default=None, ge=0, le=4)
    max_price_minor: int | None = Field(default=None, gt=0)
    departure_time_from: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    departure_time_to: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")

    @model_validator(mode="after")
    def normalize_currency(self) -> FiltersInput:
        self.currency = self.currency.upper()
        return self


class ScheduleInput(StrictModel):
    interval_minutes: int = Field(default=720, ge=5, le=10080)


class AlertsInput(StrictModel):
    new_historical_low: bool = False
    price_below_minor: int | None = Field(default=None, gt=0)


class MockSourceConfiguration(StrictModel):
    schema_version: Literal["1"] = "1"
    mode: Literal["success", "error", "timeout", "empty"] = "success"
    base_price_minor: int | None = Field(default=None, gt=0, le=1_000_000_000)
    duplicate_first: bool = False


class MonitorCreate(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    route: RouteInput
    departure_dates: list[date] = Field(min_length=1, max_length=31)
    return_dates: list[date] | None = Field(default=None, max_length=31)
    passengers: PassengersInput = Field(default_factory=PassengersInput)
    filters: FiltersInput = Field(default_factory=FiltersInput)
    sources: list[str] = Field(min_length=1, max_length=10, examples=[["mock"]])
    source_configuration: dict[str, MockSourceConfiguration] = Field(
        default_factory=dict,
        max_length=10,
        description=(
            "Per-source configuration. The first release exposes only the strict MockSource "
            "contract; future adapters add versioned schemas before accepting configuration."
        ),
    )
    schedule: ScheduleInput = Field(default_factory=ScheduleInput)
    alerts: AlertsInput = Field(default_factory=AlertsInput)

    @model_validator(mode="after")
    def validate_date_windows_and_sources(self) -> MonitorCreate:
        if len(set(self.departure_dates)) != len(self.departure_dates):
            raise ValueError("departure_dates cannot contain duplicates")
        if self.return_dates is not None:
            if len(self.return_dates) != len(self.departure_dates):
                raise ValueError("return_dates must pair one-to-one with departure_dates")
            if any(
                returned <= departed
                for departed, returned in zip(
                    self.departure_dates,
                    self.return_dates,
                    strict=True,
                )
            ):
                raise ValueError("each return date must be after its paired departure date")
        normalized_sources = [source.strip().lower() for source in self.sources]
        if len(set(normalized_sources)) != len(normalized_sources):
            raise ValueError("sources cannot contain duplicates")
        self.sources = normalized_sources
        unknown_options = set(self.source_configuration) - set(normalized_sources)
        if unknown_options:
            raise ValueError("source_configuration contains a source not selected in sources")
        return self

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [
                {
                    "name": "Brasília para Porto Velho",
                    "route": {"origin": "BSB", "destination": "PVH"},
                    "departure_dates": ["2030-07-10", "2030-07-11"],
                    "passengers": {"adults": 1, "children": 0, "infants": 0},
                    "filters": {
                        "currency": "BRL",
                        "max_stops": 1,
                        "max_price_minor": 100000,
                    },
                    "sources": ["mock"],
                    "schedule": {"interval_minutes": 720},
                    "alerts": {
                        "new_historical_low": True,
                        "price_below_minor": 100000,
                    },
                }
            ]
        },
    )


class MonitorRead(StrictModel):
    id: str
    name: str
    origin_iata: str
    destination_iata: str
    departure_dates: list[date]
    return_dates: list[date] | None
    trip_type: str
    adults: int
    children: int
    infants: int
    cabin_class: str
    currency: str
    max_price_minor: int | None
    max_stops: int | None
    check_interval_minutes: int
    is_active: bool
    next_run_at: datetime | None
    sources: list[str]
    created_at: datetime
    updated_at: datetime


class RunQueued(StrictModel):
    run_id: str
    status: str


class SourceRunRead(StrictModel):
    id: str
    source_name: str
    source_kind: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    quota_cost: int
    error_code: str | None
    error_message: str | None


class RunRead(StrictModel):
    id: str
    monitor_id: str
    trigger: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    offers_received: int
    sources_requested: int
    sources_succeeded: int
    sources_failed: int
    error_summary: dict[str, Any] | None
    created_at: datetime
    source_runs: list[SourceRunRead]


class SegmentRead(StrictModel):
    leg_index: int
    sequence: int
    origin: str
    destination: str
    departure_at: datetime
    arrival_at: datetime
    marketing_airline: str | None
    operating_airline: str | None
    flight_number: str | None


class OfferRead(StrictModel):
    quote_id: str
    itinerary_id: str
    itinerary_hash: str
    source_name: str
    source_offer_id: str | None
    price_minor: int
    currency: str
    booking_url: str | None
    baggage_summary: str | None
    fare_brand: str | None
    confidence_score: float
    observed_at: datetime
    stops: int
    duration_minutes: int
    segments: list[SegmentRead]


class PriceHistoryRead(StrictModel):
    observation_id: str
    quote_id: str
    run_id: str
    source_run_id: str
    source_name: str
    price_minor: int
    currency: str
    observed_at: datetime


class AlertEventRead(StrictModel):
    id: str
    monitor_id: str
    alert_rule_id: str | None
    search_run_id: str | None
    quote_observation_id: str | None
    rule_type: str
    status: str
    message: str | None
    provider: str | None
    provider_message_id: str | None
    attempt_count: int
    last_attempt_at: datetime | None
    suppression_reason: str | None
    error_message: str | None
    created_at: datetime
    sent_at: datetime | None


class SourceRead(StrictModel):
    name: str
    kind: str
    version: str
    parser_version: str
    enabled: bool
    healthy: bool | None
    capabilities: dict[str, bool]


class HealthRead(StrictModel):
    status: str
    version: str


class ReadyRead(StrictModel):
    status: str
    checks: dict[str, str]


class VersionRead(StrictModel):
    name: str
    version: str
