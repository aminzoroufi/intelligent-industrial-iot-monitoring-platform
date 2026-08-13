# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""Register versioned per-device anomaly models and scoring health."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260811_0004"
down_revision = "20260811_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "anomaly_models",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "device_id",
            sa.String(63),
            sa.ForeignKey("devices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("model_version", sa.String(80), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("feature_schema", sa.JSON(), nullable=False),
        sa.Column("training_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("training_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("training_sample_count", sa.Integer(), nullable=False),
        sa.Column("validation_sample_count", sa.Integer(), nullable=False),
        sa.Column("contamination", sa.Float(), nullable=False),
        sa.Column("random_seed", sa.Integer(), nullable=False),
        sa.Column("sklearn_version", sa.String(32), nullable=False),
        sa.Column("artifact_path", sa.String(300), nullable=False),
        sa.Column("artifact_checksum", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_scored_at", sa.DateTime(timezone=True)),
        sa.Column("diagnostic", sa.String(300)),
        sa.UniqueConstraint("device_id", "model_version", name="uq_anomaly_device_version"),
    )
    op.create_index("ix_anomaly_device_created", "anomaly_models", ["device_id", "created_at"])


def downgrade() -> None:
    op.drop_table("anomaly_models")
