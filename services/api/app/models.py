# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""Relational persistence model for condition monitoring and audit workflows."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.api.app.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="operator")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(63), primary_key=True)
    site_id: Mapped[str] = mapped_column(String(63), index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    asset_class: Mapped[str] = mapped_column(String(80), default="dc-motor")
    simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    firmware_version: Mapped[str | None] = mapped_column(String(48))
    reported_status: Mapped[str] = mapped_column(String(20), default="offline")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    rssi_dbm: Mapped[int | None] = mapped_column(Integer)
    reset_reason: Mapped[str | None] = mapped_column(String(48))
    reset_count: Mapped[int] = mapped_column(Integer, default=0)
    queue_depth: Mapped[int] = mapped_column(Integer, default=0)
    queue_capacity: Mapped[int] = mapped_column(Integer, default=512)
    dropped_message_count: Mapped[int] = mapped_column(Integer, default=0)
    modbus_status: Mapped[str] = mapped_column(String(20), default="disabled")
    active_faults: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    telemetry: Mapped[list[Telemetry]] = relationship(back_populates="device")


class Telemetry(Base):
    __tablename__ = "telemetry"
    __table_args__ = (
        UniqueConstraint("device_id", "sequence", name="uq_telemetry_device_sequence"),
        Index("ix_telemetry_device_received", "device_id", "received_at"),
        Index("ix_telemetry_device_device_time", "device_id", "device_time"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    site_id: Mapped[str] = mapped_column(String(63), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    device_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    clock_synchronized: Mapped[bool] = mapped_column(Boolean)
    uptime_ms: Mapped[int] = mapped_column(Integer)
    firmware_version: Mapped[str] = mapped_column(String(48))
    quality: Mapped[str] = mapped_column(String(20))
    replayed: Mapped[bool] = mapped_column(Boolean, default=False)
    temperature_c: Mapped[float | None] = mapped_column(Float)
    vibration_rms_mps2: Mapped[float | None] = mapped_column(Float)
    vibration_peak_mps2: Mapped[float | None] = mapped_column(Float)
    vibration_crest_factor: Mapped[float | None] = mapped_column(Float)
    current_a: Mapped[float | None] = mapped_column(Float)
    sample_quality: Mapped[dict[str, object]] = mapped_column(JSON)
    fault_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    anomaly_score: Mapped[float | None] = mapped_column(Float)
    anomaly_percentile: Mapped[float | None] = mapped_column(Float)
    anomaly_reason: Mapped[str | None] = mapped_column(String(300))

    device: Mapped[Device] = relationship(back_populates="telemetry")


class HealthSnapshot(Base):
    __tablename__ = "health_snapshots"
    __table_args__ = (Index("ix_health_device_received", "device_id", "received_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[str] = mapped_column(String(36), unique=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    payload: Mapped[dict[str, object]] = mapped_column(JSON)


class Alarm(Base):
    __tablename__ = "alarms"
    __table_args__ = (Index("ix_alarm_device_opened", "device_id", "opened_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(48))
    severity: Mapped[str] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(24), default="threshold")
    state: Mapped[str] = mapped_column(String(16), default="active")
    summary: Mapped[str] = mapped_column(String(240))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by: Mapped[str | None] = mapped_column(String(80))


class Calibration(Base):
    __tablename__ = "calibrations"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    sensor: Mapped[str] = mapped_column(String(32))
    previous_coefficients: Mapped[dict[str, float]] = mapped_column(JSON)
    new_coefficients: Mapped[dict[str, float]] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(String(240))
    operator: Mapped[str] = mapped_column(String(80))
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class MaintenanceRecord(Base):
    __tablename__ = "maintenance_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(24))
    notes: Mapped[str] = mapped_column(Text)
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    next_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(80))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_actor_created", "actor", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(80))
    target_type: Mapped[str] = mapped_column(String(48))
    target_id: Mapped[str] = mapped_column(String(80))
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ErrorLog(Base):
    __tablename__ = "error_logs"
    __table_args__ = (Index("ix_error_component_created", "component", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    component: Mapped[str] = mapped_column(String(48))
    error_code: Mapped[str] = mapped_column(String(48))
    severity: Mapped[str] = mapped_column(String(16))
    device_id: Mapped[str | None] = mapped_column(String(63))
    detail: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
