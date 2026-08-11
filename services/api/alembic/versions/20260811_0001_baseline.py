# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""Create the baseline monitoring, maintenance, and audit schema."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260811_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(80), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "devices",
        sa.Column("id", sa.String(63), primary_key=True),
        sa.Column("site_id", sa.String(63), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("asset_class", sa.String(80), nullable=False),
        sa.Column("simulated", sa.Boolean(), nullable=False),
        sa.Column("firmware_version", sa.String(48)),
        sa.Column("reported_status", sa.String(20), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("rssi_dbm", sa.Integer()),
        sa.Column("reset_reason", sa.String(48)),
        sa.Column("reset_count", sa.Integer(), nullable=False),
        sa.Column("queue_depth", sa.Integer(), nullable=False),
        sa.Column("queue_capacity", sa.Integer(), nullable=False),
        sa.Column("dropped_message_count", sa.Integer(), nullable=False),
        sa.Column("modbus_status", sa.String(20), nullable=False),
        sa.Column("active_faults", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_devices_site_id", "devices", ["site_id"])
    op.create_index("ix_devices_last_seen_at", "devices", ["last_seen_at"])

    op.create_table(
        "telemetry",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message_id", sa.String(36), nullable=False),
        sa.Column(
            "device_id",
            sa.String(63),
            sa.ForeignKey("devices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("site_id", sa.String(63), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("device_time", sa.DateTime(timezone=True)),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("clock_synchronized", sa.Boolean(), nullable=False),
        sa.Column("uptime_ms", sa.Integer(), nullable=False),
        sa.Column("firmware_version", sa.String(48), nullable=False),
        sa.Column("quality", sa.String(20), nullable=False),
        sa.Column("replayed", sa.Boolean(), nullable=False),
        sa.Column("temperature_c", sa.Float()),
        sa.Column("vibration_rms_mps2", sa.Float()),
        sa.Column("vibration_peak_mps2", sa.Float()),
        sa.Column("vibration_crest_factor", sa.Float()),
        sa.Column("current_a", sa.Float()),
        sa.Column("sample_quality", sa.JSON(), nullable=False),
        sa.Column("fault_flags", sa.JSON(), nullable=False),
        sa.Column("anomaly_score", sa.Float()),
        sa.Column("anomaly_percentile", sa.Float()),
        sa.Column("anomaly_reason", sa.String(300)),
        sa.UniqueConstraint("message_id"),
        sa.UniqueConstraint("device_id", "sequence", name="uq_telemetry_device_sequence"),
    )
    op.create_index("ix_telemetry_message_id", "telemetry", ["message_id"], unique=True)
    op.create_index("ix_telemetry_site_id", "telemetry", ["site_id"])
    op.create_index("ix_telemetry_device_received", "telemetry", ["device_id", "received_at"])
    op.create_index("ix_telemetry_device_device_time", "telemetry", ["device_id", "device_time"])

    op.create_table(
        "health_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message_id", sa.String(36), nullable=False, unique=True),
        sa.Column(
            "device_id",
            sa.String(63),
            sa.ForeignKey("devices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index("ix_health_device_received", "health_snapshots", ["device_id", "received_at"])

    op.create_table(
        "alarms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "device_id",
            sa.String(63),
            sa.ForeignKey("devices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(48), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("source", sa.String(24), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("summary", sa.String(240), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cleared_at", sa.DateTime(timezone=True)),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("acknowledged_by", sa.String(80)),
    )
    op.create_index("ix_alarm_device_opened", "alarms", ["device_id", "opened_at"])

    op.create_table(
        "calibrations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "device_id",
            sa.String(63),
            sa.ForeignKey("devices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sensor", sa.String(32), nullable=False),
        sa.Column("previous_coefficients", sa.JSON(), nullable=False),
        sa.Column("new_coefficients", sa.JSON(), nullable=False),
        sa.Column("reason", sa.String(240), nullable=False),
        sa.Column("operator", sa.String(80), nullable=False),
        sa.Column("performed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_calibrations_device_id", "calibrations", ["device_id"])

    op.create_table(
        "maintenance_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "device_id",
            sa.String(63),
            sa.ForeignKey("devices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("performed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_due_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.String(80), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_maintenance_records_device_id", "maintenance_records", ["device_id"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor", sa.String(80), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("target_type", sa.String(48), nullable=False),
        sa.Column("target_id", sa.String(80), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_actor_created", "audit_events", ["actor", "created_at"])

    op.create_table(
        "error_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("component", sa.String(48), nullable=False),
        sa.Column("error_code", sa.String(48), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("device_id", sa.String(63)),
        sa.Column("detail", sa.String(300), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_error_component_created", "error_logs", ["component", "created_at"])


def downgrade() -> None:
    op.drop_table("error_logs")
    op.drop_table("audit_events")
    op.drop_table("maintenance_records")
    op.drop_table("calibrations")
    op.drop_table("alarms")
    op.drop_table("health_snapshots")
    op.drop_table("telemetry")
    op.drop_table("devices")
    op.drop_table("users")
