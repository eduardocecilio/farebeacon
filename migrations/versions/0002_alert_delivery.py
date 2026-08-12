"""Add alert evaluation and notification delivery state.

Revision ID: 0002_alert_delivery
Revises: 0001_initial
Create Date: 2026-08-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_alert_delivery"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "alert_events",
        sa.Column("alert_rule_id", sa.String(40), sa.ForeignKey("alert_rules.id"), nullable=True),
    )
    op.add_column(
        "alert_events",
        sa.Column("search_run_id", sa.String(40), sa.ForeignKey("search_runs.id"), nullable=True),
    )
    op.add_column("alert_events", sa.Column("message", sa.Text(), nullable=True))
    op.add_column("alert_events", sa.Column("provider", sa.String(30), nullable=True))
    op.add_column(
        "alert_events",
        sa.Column("provider_message_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "alert_events",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "alert_events",
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("alert_events", sa.Column("suppression_reason", sa.Text(), nullable=True))
    op.create_index("ix_alert_events_alert_rule_id", "alert_events", ["alert_rule_id"])
    op.create_index("ix_alert_events_search_run_id", "alert_events", ["search_run_id"])


def downgrade() -> None:
    op.drop_index("ix_alert_events_search_run_id", table_name="alert_events")
    op.drop_index("ix_alert_events_alert_rule_id", table_name="alert_events")
    for column in (
        "suppression_reason",
        "last_attempt_at",
        "attempt_count",
        "provider_message_id",
        "provider",
        "message",
        "search_run_id",
        "alert_rule_id",
    ):
        op.drop_column("alert_events", column)
