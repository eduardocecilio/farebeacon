"""Create the initial FareBeacon schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "monitors",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("origin_iata", sa.String(3), nullable=False),
        sa.Column("destination_iata", sa.String(3), nullable=False),
        sa.Column("departure_dates", sa.JSON(), nullable=False),
        sa.Column("return_dates", sa.JSON(), nullable=True),
        sa.Column("trip_type", sa.String(20), nullable=False),
        sa.Column("adults", sa.Integer(), nullable=False),
        sa.Column("children", sa.Integer(), nullable=False),
        sa.Column("infants", sa.Integer(), nullable=False),
        sa.Column("cabin_class", sa.String(30), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("max_price_minor", sa.Integer(), nullable=True),
        sa.Column("max_stops", sa.Integer(), nullable=True),
        sa.Column("departure_time_from", sa.String(5), nullable=True),
        sa.Column("departure_time_to", sa.String(5), nullable=True),
        sa.Column("check_interval_minutes", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("adults >= 1", name="ck_monitor_adults_positive"),
        sa.CheckConstraint("children >= 0", name="ck_monitor_children_nonnegative"),
        sa.CheckConstraint("infants >= 0", name="ck_monitor_infants_nonnegative"),
        sa.CheckConstraint("check_interval_minutes >= 5", name="ck_monitor_interval_minimum"),
    )
    op.create_index("ix_monitors_origin_iata", "monitors", ["origin_iata"])
    op.create_index("ix_monitors_destination_iata", "monitors", ["destination_iata"])
    op.create_index("ix_monitors_is_active", "monitors", ["is_active"])

    op.create_table(
        "source_definitions",
        sa.Column("name", sa.String(100), primary_key=True),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("max_concurrency", sa.Integer(), nullable=False),
        sa.Column("cache_ttl_minutes", sa.Integer(), nullable=False),
        sa.Column("parser_version", sa.String(50), nullable=True),
        sa.Column("monthly_budget", sa.Integer(), nullable=True),
        sa.Column("daily_budget", sa.Integer(), nullable=True),
        sa.Column("reserve", sa.Integer(), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("success_rate", sa.Numeric(5, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "itineraries",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("itinerary_hash", sa.String(80), nullable=False),
        sa.Column("origin_iata", sa.String(3), nullable=False),
        sa.Column("destination_iata", sa.String(3), nullable=False),
        sa.Column("departure_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("arrival_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("stops", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("itinerary_hash", name="uq_itinerary_hash"),
        sa.CheckConstraint("stops >= 0", name="ck_itinerary_stops_nonnegative"),
    )
    op.create_index("ix_itineraries_itinerary_hash", "itineraries", ["itinerary_hash"])
    op.create_index("ix_itineraries_origin_iata", "itineraries", ["origin_iata"])
    op.create_index("ix_itineraries_destination_iata", "itineraries", ["destination_iata"])
    op.create_index("ix_itineraries_departure_at", "itineraries", ["departure_at"])

    op.create_table(
        "raw_artifacts",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("artifact_type", sa.String(30), nullable=False),
        sa.Column("storage_backend", sa.String(30), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False, unique=True),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("is_sanitized", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("scope", sa.String(255), nullable=False),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.String(40), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("scope", "key", name="uq_idempotency_scope_key"),
    )
    op.create_index("ix_idempotency_records_expires_at", "idempotency_records", ["expires_at"])

    op.create_table(
        "monitor_sources",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column(
            "monitor_id",
            sa.String(40),
            sa.ForeignKey("monitors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_name",
            sa.String(100),
            sa.ForeignKey("source_definitions.name"),
            nullable=False,
        ),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("monitor_id", "source_name", name="uq_monitor_source"),
    )
    op.create_index("ix_monitor_sources_monitor_id", "monitor_sources", ["monitor_id"])
    op.create_index("ix_monitor_sources_source_name", "monitor_sources", ["source_name"])

    op.create_table(
        "search_runs",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("monitor_id", sa.String(40), sa.ForeignKey("monitors.id"), nullable=False),
        sa.Column("trigger", sa.String(20), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("offers_received", sa.Integer(), nullable=False),
        sa.Column("sources_requested", sa.Integer(), nullable=False),
        sa.Column("sources_succeeded", sa.Integer(), nullable=False),
        sa.Column("sources_failed", sa.Integer(), nullable=False),
        sa.Column("error_summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_search_runs_monitor_id", "search_runs", ["monitor_id"])
    op.create_index("ix_search_runs_status", "search_runs", ["status"])
    op.create_index("ix_search_runs_monitor_created", "search_runs", ["monitor_id", "created_at"])

    op.create_table(
        "flight_segments",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column(
            "itinerary_id",
            sa.String(40),
            sa.ForeignKey("itineraries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("leg_index", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("origin_iata", sa.String(3), nullable=False),
        sa.Column("destination_iata", sa.String(3), nullable=False),
        sa.Column("departure_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("arrival_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("marketing_airline", sa.String(10), nullable=True),
        sa.Column("operating_airline", sa.String(10), nullable=True),
        sa.Column("flight_number", sa.String(20), nullable=True),
        sa.UniqueConstraint(
            "itinerary_id",
            "leg_index",
            "sequence",
            name="uq_segment_sequence",
        ),
    )
    op.create_index("ix_flight_segments_itinerary_id", "flight_segments", ["itinerary_id"])

    op.create_table(
        "quotes",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column(
            "itinerary_id",
            sa.String(40),
            sa.ForeignKey("itineraries.id"),
            nullable=False,
        ),
        sa.Column("source_name", sa.String(100), nullable=False),
        sa.Column("source_offer_id", sa.String(255), nullable=True),
        sa.Column("quote_fingerprint", sa.String(64), nullable=False),
        sa.Column("price_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("booking_url", sa.Text(), nullable=True),
        sa.Column("baggage_summary", sa.Text(), nullable=True),
        sa.Column("fare_brand", sa.String(100), nullable=True),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("quote_fingerprint", name="uq_quote_fingerprint"),
        sa.CheckConstraint("price_minor > 0", name="ck_quote_price_positive"),
    )
    op.create_index("ix_quotes_itinerary_id", "quotes", ["itinerary_id"])
    op.create_index("ix_quotes_source_name", "quotes", ["source_name"])
    op.create_index("ix_quotes_quote_fingerprint", "quotes", ["quote_fingerprint"])

    op.create_table(
        "alert_rules",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column(
            "monitor_id",
            sa.String(40),
            sa.ForeignKey("monitors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rule_type", sa.String(50), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_alert_rules_monitor_id", "alert_rules", ["monitor_id"])

    op.create_table(
        "source_runs",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column(
            "search_run_id",
            sa.String(40),
            sa.ForeignKey("search_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_name", sa.String(100), nullable=False),
        sa.Column("source_kind", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quota_cost", sa.Integer(), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("parser_version", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("search_run_id", "source_name", name="uq_run_source"),
    )
    op.create_index("ix_source_runs_search_run_id", "source_runs", ["search_run_id"])
    op.create_index("ix_source_runs_source_name", "source_runs", ["source_name"])
    op.create_index("ix_source_runs_status", "source_runs", ["status"])
    op.create_index("ix_source_runs_search_status", "source_runs", ["search_run_id", "status"])

    op.create_table(
        "quote_observations",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("quote_id", sa.String(40), sa.ForeignKey("quotes.id"), nullable=False),
        sa.Column(
            "search_run_id",
            sa.String(40),
            sa.ForeignKey("search_runs.id"),
            nullable=False,
        ),
        sa.Column(
            "source_run_id",
            sa.String(40),
            sa.ForeignKey("source_runs.id"),
            nullable=False,
        ),
        sa.Column("price_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "raw_artifact_id",
            sa.String(40),
            sa.ForeignKey("raw_artifacts.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("quote_id", "source_run_id", name="uq_quote_observation_run"),
        sa.CheckConstraint("price_minor > 0", name="ck_observation_price_positive"),
    )
    op.create_index("ix_quote_observations_quote_id", "quote_observations", ["quote_id"])
    op.create_index("ix_quote_observations_search_run_id", "quote_observations", ["search_run_id"])
    op.create_index("ix_quote_observations_source_run_id", "quote_observations", ["source_run_id"])
    op.create_index("ix_quote_observations_observed_at", "quote_observations", ["observed_at"])
    op.create_index(
        "ix_observation_quote_observed",
        "quote_observations",
        ["quote_id", "observed_at"],
    )

    op.create_table(
        "alert_events",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("monitor_id", sa.String(40), sa.ForeignKey("monitors.id"), nullable=False),
        sa.Column(
            "quote_observation_id",
            sa.String(40),
            sa.ForeignKey("quote_observations.id"),
            nullable=True,
        ),
        sa.Column("rule_type", sa.String(50), nullable=False),
        sa.Column("deduplication_key", sa.String(128), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.UniqueConstraint("deduplication_key", name="uq_alert_deduplication"),
    )
    op.create_index("ix_alert_events_monitor_id", "alert_events", ["monitor_id"])


def downgrade() -> None:
    for table in (
        "alert_events",
        "quote_observations",
        "source_runs",
        "alert_rules",
        "quotes",
        "flight_segments",
        "search_runs",
        "monitor_sources",
        "idempotency_records",
        "raw_artifacts",
        "itineraries",
        "source_definitions",
        "monitors",
    ):
        op.drop_table(table)
