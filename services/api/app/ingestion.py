# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""Idempotent persistence for validated telemetry envelopes."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.api.app.events import notify_after_commit
from services.api.app.models import (
    Alarm,
    AuditEvent,
    Device,
    DeviceCommand,
    HealthSnapshot,
    Telemetry,
    ThresholdConfig,
    utc_now,
)
from services.api.app.schemas import CommandAckEnvelope, HealthEnvelope, TelemetryEnvelope


@dataclass(frozen=True)
class PersistResult:
    status: str
    message_id: str


class SequenceCollisionError(ValueError):
    """The device reused a sequence for a different globally unique message."""


def _threshold_summary(metric: str, value: float, severity: str, unit: str) -> str:
    label = metric.replace("_", " ")
    return f"{label.capitalize()} is {value:.3g} {unit}; {severity} threshold is active."


def _apply_metric_alarm(
    session: Session,
    *,
    device_id: str,
    code: str,
    metric: str,
    unit: str,
    value: float | None,
    warning: float,
    critical: float,
    hysteresis_percent: float,
) -> None:
    if value is None:
        return
    active = session.scalar(
        select(Alarm).where(
            Alarm.device_id == device_id,
            Alarm.code == code,
            Alarm.state == "active",
        )
    )
    desired: str | None
    if value >= critical:
        desired = "critical"
    elif value >= warning:
        desired = "warning"
    else:
        desired = None

    now = utc_now()
    if desired is not None:
        summary = _threshold_summary(metric, value, desired, unit)
        if active is None:
            session.add(
                Alarm(
                    device_id=device_id,
                    code=code,
                    severity=desired,
                    source="threshold",
                    state="active",
                    summary=summary,
                    opened_at=now,
                )
            )
        else:
            active.severity = desired
            active.summary = summary
        return

    clear_below = warning * (1 - hysteresis_percent / 100)
    if active is not None and value < clear_below:
        active.state = "cleared"
        active.cleared_at = now


def apply_threshold_alarms(session: Session, device: Device, envelope: TelemetryEnvelope) -> None:
    config = session.get(ThresholdConfig, device.id)
    if config is None:
        config = ThresholdConfig(device_id=device.id)
        session.add(config)
        session.flush()
    values = envelope.measurements
    _apply_metric_alarm(
        session,
        device_id=device.id,
        code="TEMPERATURE_THRESHOLD",
        metric="temperature",
        unit="deg C",
        value=values.temperature_c,
        warning=config.temperature_warning_c,
        critical=config.temperature_critical_c,
        hysteresis_percent=config.hysteresis_percent,
    )
    _apply_metric_alarm(
        session,
        device_id=device.id,
        code="VIBRATION_THRESHOLD",
        metric="vibration RMS",
        unit="m/s^2",
        value=values.vibration_rms_mps2,
        warning=config.vibration_warning_mps2,
        critical=config.vibration_critical_mps2,
        hysteresis_percent=config.hysteresis_percent,
    )
    _apply_metric_alarm(
        session,
        device_id=device.id,
        code="CURRENT_THRESHOLD",
        metric="current",
        unit="A",
        value=values.current_a,
        warning=config.current_warning_a,
        critical=config.current_critical_a,
        hysteresis_percent=config.hysteresis_percent,
    )


def persist_telemetry(session: Session, envelope: TelemetryEnvelope) -> PersistResult:
    message_id = str(envelope.message_id)
    existing = session.scalar(select(Telemetry).where(Telemetry.message_id == message_id))
    if existing is not None:
        return PersistResult(status="duplicate", message_id=message_id)

    sequence_owner = session.scalar(
        select(Telemetry).where(
            Telemetry.device_id == envelope.device_id,
            Telemetry.sequence == envelope.sequence,
        )
    )
    if sequence_owner is not None:
        raise SequenceCollisionError(
            f"sequence {envelope.sequence} already belongs to another message"
        )

    device = session.get(Device, envelope.device_id)
    if device is None:
        device = Device(
            id=envelope.device_id,
            site_id=envelope.site_id,
            display_name=envelope.device_id,
            simulated=True,
        )
        session.add(device)
    elif device.site_id != envelope.site_id:
        raise ValueError("topic site does not match registered device site")

    now = utc_now()
    device.last_seen_at = now
    device.firmware_version = envelope.firmware_version
    device.reported_status = "degraded" if envelope.quality != "good" else "online"
    device.active_faults = list(envelope.fault_flags)

    values = envelope.measurements
    row = Telemetry(
        message_id=message_id,
        device_id=envelope.device_id,
        site_id=envelope.site_id,
        sequence=envelope.sequence,
        device_time=envelope.device_time,
        received_at=now,
        clock_synchronized=envelope.clock_synchronized,
        uptime_ms=envelope.uptime_ms,
        firmware_version=envelope.firmware_version,
        quality=envelope.quality,
        replayed=envelope.replayed,
        temperature_c=values.temperature_c,
        vibration_rms_mps2=values.vibration_rms_mps2,
        vibration_peak_mps2=values.vibration_peak_mps2,
        vibration_crest_factor=values.vibration_crest_factor,
        current_a=values.current_a,
        sample_quality=envelope.sample_quality.model_dump(mode="json"),
        fault_flags=list(envelope.fault_flags),
    )
    session.add(row)
    apply_threshold_alarms(session, device, envelope)
    notify_after_commit(
        session,
        {
            "type": "telemetry",
            "device_id": envelope.device_id,
            "message_id": message_id,
            "sequence": envelope.sequence,
            "quality": envelope.quality,
            "measurements": envelope.measurements.model_dump(mode="json"),
            "fault_flags": envelope.fault_flags,
        },
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.scalar(select(Telemetry).where(Telemetry.message_id == message_id))
        if existing is not None:
            return PersistResult(status="duplicate", message_id=message_id)
        raise
    return PersistResult(status="inserted", message_id=message_id)


def persist_health(session: Session, envelope: HealthEnvelope) -> PersistResult:
    message_id = str(envelope.message_id)
    if session.scalar(select(HealthSnapshot).where(HealthSnapshot.message_id == message_id)):
        return PersistResult(status="duplicate", message_id=message_id)

    device = session.get(Device, envelope.device_id)
    if device is None:
        device = Device(
            id=envelope.device_id,
            site_id=envelope.site_id,
            display_name=envelope.device_id,
            simulated=True,
        )
        session.add(device)
    elif device.site_id != envelope.site_id:
        raise ValueError("topic site does not match registered device site")

    device.firmware_version = envelope.firmware_version
    device.reported_status = envelope.status
    device.last_seen_at = utc_now()
    device.rssi_dbm = envelope.rssi_dbm
    device.reset_reason = envelope.reset_reason
    device.reset_count = envelope.reset_count
    device.queue_depth = envelope.queue_depth
    device.queue_capacity = envelope.queue_capacity
    device.dropped_message_count = envelope.dropped_message_count
    device.modbus_status = envelope.modbus_status
    device.active_faults = envelope.active_faults
    session.add(
        HealthSnapshot(
            message_id=message_id,
            device_id=envelope.device_id,
            payload=envelope.model_dump(mode="json"),
        )
    )
    notify_after_commit(
        session,
        {
            "type": "health",
            "device_id": envelope.device_id,
            "status": envelope.status,
            "queue_depth": envelope.queue_depth,
            "modbus_status": envelope.modbus_status,
            "active_faults": envelope.active_faults,
        },
    )
    session.commit()
    return PersistResult(status="inserted", message_id=message_id)


def persist_command_ack(session: Session, envelope: CommandAckEnvelope) -> PersistResult:
    message_id = str(envelope.message_id)
    command = session.get(DeviceCommand, str(envelope.command_id))
    if command is None:
        raise ValueError("acknowledgement references an unknown command")
    if command.device_id != envelope.device_id:
        raise ValueError("acknowledgement device does not match command")
    if command.acknowledged_at is not None and command.status == envelope.status:
        return PersistResult(status="duplicate", message_id=message_id)

    command.status = envelope.status
    command.result_code = envelope.result_code
    command.detail = envelope.detail
    command.acknowledged_at = utc_now()
    session.add(
        AuditEvent(
            actor=envelope.device_id,
            action="command_acknowledged",
            target_type="device_command",
            target_id=command.command_id,
            details={
                "status": envelope.status,
                "result_code": envelope.result_code,
                "relay_on": envelope.relay_on,
            },
        )
    )
    notify_after_commit(
        session,
        {
            "type": "command_ack",
            "device_id": envelope.device_id,
            "command_id": command.command_id,
            "status": envelope.status,
            "result_code": envelope.result_code,
            "relay_on": envelope.relay_on,
        },
    )
    session.commit()
    return PersistResult(status="inserted", message_id=message_id)
