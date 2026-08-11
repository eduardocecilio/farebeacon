from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from farebeacon.domain.enums import (
    AlertEventStatus,
    RunStatus,
    RunTrigger,
    SourceKind,
    SourceRunStatus,
    SourceStatus,
    TripType,
)
from farebeacon.ids import new_id


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class Monitor(TimestampMixin, Base):
    __tablename__ = "monitors"
    __table_args__ = (
        CheckConstraint("adults >= 1", name="ck_monitor_adults_positive"),
        CheckConstraint("children >= 0", name="ck_monitor_children_nonnegative"),
        CheckConstraint("infants >= 0", name="ck_monitor_infants_nonnegative"),
        CheckConstraint("check_interval_minutes >= 5", name="ck_monitor_interval_minimum"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("mon"))
    name: Mapped[str] = mapped_column(String(200))
    origin_iata: Mapped[str] = mapped_column(String(3), index=True)
    destination_iata: Mapped[str] = mapped_column(String(3), index=True)
    departure_dates: Mapped[list[str]] = mapped_column(JSON)
    return_dates: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    trip_type: Mapped[str] = mapped_column(String(20), default=TripType.ONE_WAY.value)
    adults: Mapped[int] = mapped_column(Integer, default=1)
    children: Mapped[int] = mapped_column(Integer, default=0)
    infants: Mapped[int] = mapped_column(Integer, default=0)
    cabin_class: Mapped[str] = mapped_column(String(30), default="economy")
    currency: Mapped[str] = mapped_column(String(3), default="BRL")
    max_price_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_stops: Mapped[int | None] = mapped_column(Integer, nullable=True)
    departure_time_from: Mapped[str | None] = mapped_column(String(5), nullable=True)
    departure_time_to: Mapped[str | None] = mapped_column(String(5), nullable=True)
    check_interval_minutes: Mapped[int] = mapped_column(Integer, default=720)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sources: Mapped[list[MonitorSource]] = relationship(
        back_populates="monitor",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    alert_rules: Mapped[list[AlertRule]] = relationship(
        back_populates="monitor",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    runs: Mapped[list[SearchRun]] = relationship(back_populates="monitor")


class SourceDefinition(Base):
    __tablename__ = "source_definitions"

    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    kind: Mapped[str] = mapped_column(String(30), default=SourceKind.MOCK.value)
    version: Mapped[str] = mapped_column(String(50))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(30), default=SourceStatus.UNKNOWN.value)
    capabilities: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30)
    max_concurrency: Mapped[int] = mapped_column(Integer, default=2)
    cache_ttl_minutes: Mapped[int] = mapped_column(Integer, default=0)
    parser_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    monthly_budget: Mapped[int | None] = mapped_column(Integer, nullable=True)
    daily_budget: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reserve: Mapped[int] = mapped_column(Integer, default=0)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    success_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class MonitorSource(TimestampMixin, Base):
    __tablename__ = "monitor_sources"
    __table_args__ = (UniqueConstraint("monitor_id", "source_name", name="uq_monitor_source"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("msrc"))
    monitor_id: Mapped[str] = mapped_column(
        ForeignKey("monitors.id", ondelete="CASCADE"),
        index=True,
    )
    source_name: Mapped[str] = mapped_column(
        ForeignKey("source_definitions.name"),
        index=True,
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    monitor: Mapped[Monitor] = relationship(back_populates="sources")


class SearchRun(Base):
    __tablename__ = "search_runs"
    __table_args__ = (Index("ix_search_runs_monitor_created", "monitor_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("run"))
    monitor_id: Mapped[str] = mapped_column(ForeignKey("monitors.id"), index=True)
    trigger: Mapped[str] = mapped_column(String(20), default=RunTrigger.MANUAL.value)
    status: Mapped[str] = mapped_column(String(30), default=RunStatus.QUEUED.value, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    offers_received: Mapped[int] = mapped_column(Integer, default=0)
    sources_requested: Mapped[int] = mapped_column(Integer, default=0)
    sources_succeeded: Mapped[int] = mapped_column(Integer, default=0)
    sources_failed: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    monitor: Mapped[Monitor] = relationship(back_populates="runs")
    source_runs: Mapped[list[SourceRun]] = relationship(
        back_populates="search_run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class SourceRun(Base):
    __tablename__ = "source_runs"
    __table_args__ = (
        UniqueConstraint("search_run_id", "source_name", name="uq_run_source"),
        Index("ix_source_runs_search_status", "search_run_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("srun"))
    search_run_id: Mapped[str] = mapped_column(
        ForeignKey("search_runs.id", ondelete="CASCADE"),
        index=True,
    )
    source_name: Mapped[str] = mapped_column(String(100), index=True)
    source_kind: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(
        String(30),
        default=SourceRunStatus.QUEUED.value,
        index=True,
    )
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    quota_cost: Mapped[int] = mapped_column(Integer, default=0)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    parser_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    search_run: Mapped[SearchRun] = relationship(back_populates="source_runs")
    observations: Mapped[list[QuoteObservation]] = relationship(back_populates="source_run")


class Itinerary(TimestampMixin, Base):
    __tablename__ = "itineraries"
    __table_args__ = (
        UniqueConstraint("itinerary_hash", name="uq_itinerary_hash"),
        CheckConstraint("stops >= 0", name="ck_itinerary_stops_nonnegative"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("itin"))
    itinerary_hash: Mapped[str] = mapped_column(String(80), index=True)
    origin_iata: Mapped[str] = mapped_column(String(3), index=True)
    destination_iata: Mapped[str] = mapped_column(String(3), index=True)
    departure_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    arrival_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int] = mapped_column(Integer)
    stops: Mapped[int] = mapped_column(Integer)

    segments: Mapped[list[FlightSegment]] = relationship(
        back_populates="itinerary",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="FlightSegment.leg_index, FlightSegment.sequence",
    )
    quotes: Mapped[list[Quote]] = relationship(back_populates="itinerary")


class FlightSegment(Base):
    __tablename__ = "flight_segments"
    __table_args__ = (
        UniqueConstraint("itinerary_id", "leg_index", "sequence", name="uq_segment_sequence"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("seg"))
    itinerary_id: Mapped[str] = mapped_column(
        ForeignKey("itineraries.id", ondelete="CASCADE"),
        index=True,
    )
    leg_index: Mapped[int] = mapped_column(Integer, default=0)
    sequence: Mapped[int] = mapped_column(Integer)
    origin_iata: Mapped[str] = mapped_column(String(3))
    destination_iata: Mapped[str] = mapped_column(String(3))
    departure_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    arrival_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    marketing_airline: Mapped[str | None] = mapped_column(String(10), nullable=True)
    operating_airline: Mapped[str | None] = mapped_column(String(10), nullable=True)
    flight_number: Mapped[str | None] = mapped_column(String(20), nullable=True)

    itinerary: Mapped[Itinerary] = relationship(back_populates="segments")


class Quote(TimestampMixin, Base):
    __tablename__ = "quotes"
    __table_args__ = (
        UniqueConstraint("quote_fingerprint", name="uq_quote_fingerprint"),
        CheckConstraint("price_minor > 0", name="ck_quote_price_positive"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("quote"))
    itinerary_id: Mapped[str] = mapped_column(ForeignKey("itineraries.id"), index=True)
    source_name: Mapped[str] = mapped_column(String(100), index=True)
    source_offer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quote_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    price_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    booking_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    baggage_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    fare_brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 4))

    itinerary: Mapped[Itinerary] = relationship(back_populates="quotes", lazy="selectin")
    observations: Mapped[list[QuoteObservation]] = relationship(back_populates="quote")


class RawArtifact(Base):
    __tablename__ = "raw_artifacts"

    id: Mapped[str] = mapped_column(
        String(40),
        primary_key=True,
        default=lambda: new_id("art"),
    )
    artifact_type: Mapped[str] = mapped_column(String(30))
    storage_backend: Mapped[str] = mapped_column(String(30), default="local")
    storage_key: Mapped[str] = mapped_column(Text, unique=True)
    content_type: Mapped[str] = mapped_column(String(100))
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    is_sanitized: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class QuoteObservation(Base):
    __tablename__ = "quote_observations"
    __table_args__ = (
        UniqueConstraint("quote_id", "source_run_id", name="uq_quote_observation_run"),
        CheckConstraint("price_minor > 0", name="ck_observation_price_positive"),
        Index("ix_observation_quote_observed", "quote_id", "observed_at"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("obs"))
    quote_id: Mapped[str] = mapped_column(ForeignKey("quotes.id"), index=True)
    search_run_id: Mapped[str] = mapped_column(ForeignKey("search_runs.id"), index=True)
    source_run_id: Mapped[str] = mapped_column(ForeignKey("source_runs.id"), index=True)
    price_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    raw_artifact_id: Mapped[str | None] = mapped_column(
        ForeignKey("raw_artifacts.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    quote: Mapped[Quote] = relationship(back_populates="observations", lazy="selectin")
    source_run: Mapped[SourceRun] = relationship(back_populates="observations")
    raw_artifact: Mapped[RawArtifact | None] = relationship(lazy="selectin")


class AlertRule(TimestampMixin, Base):
    __tablename__ = "alert_rules"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("rule"))
    monitor_id: Mapped[str] = mapped_column(
        ForeignKey("monitors.id", ondelete="CASCADE"),
        index=True,
    )
    rule_type: Mapped[str] = mapped_column(String(50))
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    monitor: Mapped[Monitor] = relationship(back_populates="alert_rules")


class AlertEvent(Base):
    __tablename__ = "alert_events"
    __table_args__ = (UniqueConstraint("deduplication_key", name="uq_alert_deduplication"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("alert"))
    monitor_id: Mapped[str] = mapped_column(ForeignKey("monitors.id"), index=True)
    quote_observation_id: Mapped[str | None] = mapped_column(
        ForeignKey("quote_observations.id"),
        nullable=True,
    )
    rule_type: Mapped[str] = mapped_column(String(50))
    deduplication_key: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(30), default=AlertEventStatus.PENDING.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("scope", "key", name="uq_idempotency_scope_key"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("idem"))
    scope: Mapped[str] = mapped_column(String(255))
    key: Mapped[str] = mapped_column(String(255))
    request_hash: Mapped[str] = mapped_column(String(64))
    resource_type: Mapped[str] = mapped_column(String(50))
    resource_id: Mapped[str] = mapped_column(String(40))
    response_status: Mapped[int] = mapped_column(Integer)
    response_body: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
