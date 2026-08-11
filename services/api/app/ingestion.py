# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""Idempotent persistence for validated telemetry envelopes."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.api.app.models import Device, Telemetry, utc_now
from services.api.app.schemas import TelemetryEnvelope


@dataclass(frozen=True)
class PersistResult:
    status: str
    message_id: str


class SequenceCollisionError(ValueError):
    """The device reused a sequence for a different globally unique message."""


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
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.scalar(select(Telemetry).where(Telemetry.message_id == message_id))
        if existing is not None:
            return PersistResult(status="duplicate", message_id=message_id)
        raise
    return PersistResult(status="inserted", message_id=message_id)
