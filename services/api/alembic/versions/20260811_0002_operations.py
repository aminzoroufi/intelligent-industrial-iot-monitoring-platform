# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""Add threshold configuration and audited device commands."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260811_0002"
down_revision = "20260811_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "threshold_configs",
        sa.Column(
            "device_id",
            sa.String(63),
            sa.ForeignKey("devices.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("temperature_warning_c", sa.Float(), nullable=False),
        sa.Column("temperature_critical_c", sa.Float(), nullable=False),
        sa.Column("vibration_warning_mps2", sa.Float(), nullable=False),
        sa.Column("vibration_critical_mps2", sa.Float(), nullable=False),
        sa.Column("current_warning_a", sa.Float(), nullable=False),
        sa.Column("current_critical_a", sa.Float(), nullable=False),
        sa.Column("hysteresis_percent", sa.Float(), nullable=False),
        sa.Column("updated_by", sa.String(80), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "device_commands",
        sa.Column("command_id", sa.String(36), primary_key=True),
        sa.Column(
            "device_id",
            sa.String(63),
            sa.ForeignKey("devices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(48), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("result_code", sa.String(48)),
        sa.Column("detail", sa.String(240)),
        sa.Column("issued_by", sa.String(80), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_command_device_issued", "device_commands", ["device_id", "issued_at"])


def downgrade() -> None:
    op.drop_table("device_commands")
    op.drop_table("threshold_configs")
