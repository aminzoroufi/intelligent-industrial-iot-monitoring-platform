# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import BigInteger, func, select
from sqlalchemy.orm import Session, sessionmaker

from services.api.app.ingestion import (
    SequenceCollisionError,
    persist_command_ack,
    persist_health,
    persist_telemetry,
)
from services.api.app.models import Alarm, Device, DeviceCommand, HealthSnapshot, Telemetry
from services.api.app.schemas import CommandAckEnvelope, HealthEnvelope, TelemetryEnvelope

ROOT = Path(__file__).parents[3]


def load_envelope() -> TelemetryEnvelope:
    data = json.loads((ROOT / "contracts/examples/telemetry.normal.v1.json").read_text())
    return TelemetryEnvelope.model_validate(data)


def test_duplicate_message_is_idempotent(session_factory: sessionmaker[Session]) -> None:
    envelope = load_envelope()
    with session_factory() as session:
        first = persist_telemetry(session, envelope)
        second = persist_telemetry(session, envelope)
        row_count = session.scalar(select(func.count()).select_from(Telemetry))

    assert first.status == "inserted"
    assert second.status == "duplicate"
    assert row_count == 1


def test_sequence_collision_is_rejected(session_factory: sessionmaker[Session]) -> None:
    envelope = load_envelope()
    with session_factory() as session:
        persist_telemetry(session, envelope)
        colliding = envelope.model_copy(update={"message_id": uuid4()})
        with pytest.raises(SequenceCollisionError):
            persist_telemetry(session, colliding)


def test_long_running_counters_use_64_bit_storage(session_factory: sessionmaker[Session]) -> None:
    envelope = load_envelope().model_copy(
        update={
            "message_id": uuid4(),
            "sequence": 320_001,
            "uptime_ms": 3_200_020_000,
        }
    )
    assert isinstance(Telemetry.__table__.c.sequence.type, BigInteger)
    assert isinstance(Telemetry.__table__.c.uptime_ms.type, BigInteger)

    with session_factory() as session:
        persist_telemetry(session, envelope)
        row = session.scalar(select(Telemetry).where(Telemetry.sequence == 320_001))

    assert row is not None
    assert row.uptime_ms == 3_200_020_000


def test_threshold_alarm_hysteresis_transition(session_factory: sessionmaker[Session]) -> None:
    baseline = load_envelope()
    warning = baseline.model_copy(
        update={
            "message_id": uuid4(),
            "sequence": 100,
            "measurements": baseline.measurements.model_copy(update={"temperature_c": 70.0}),
        }
    )
    hold = baseline.model_copy(
        update={
            "message_id": uuid4(),
            "sequence": 101,
            "measurements": baseline.measurements.model_copy(update={"temperature_c": 63.0}),
        }
    )
    clear = baseline.model_copy(
        update={
            "message_id": uuid4(),
            "sequence": 102,
            "measurements": baseline.measurements.model_copy(update={"temperature_c": 60.0}),
        }
    )

    with session_factory() as session:
        persist_telemetry(session, warning)
        alarm = session.scalar(select(Alarm).where(Alarm.code == "TEMPERATURE_THRESHOLD"))
        assert alarm is not None
        assert alarm.severity == "warning"
        assert alarm.state == "active"

        persist_telemetry(session, hold)
        session.refresh(alarm)
        assert alarm.state == "active"

        persist_telemetry(session, clear)
        session.refresh(alarm)
        assert alarm.state == "cleared"
        assert alarm.cleared_at is not None


def test_health_snapshot_updates_device(session_factory: sessionmaker[Session]) -> None:
    data = json.loads((ROOT / "contracts/examples/health.v1.json").read_text())
    envelope = HealthEnvelope.model_validate(data)
    with session_factory() as session:
        result = persist_health(session, envelope)
        duplicate = persist_health(session, envelope)
        device = session.get(Device, "motor-01")
        count = session.scalar(select(func.count()).select_from(HealthSnapshot))

    assert result.status == "inserted"
    assert duplicate.status == "duplicate"
    assert device is not None
    assert device.rssi_dbm == -58
    assert device.modbus_status == "ok"
    assert count == 1


def test_command_ack_updates_audited_command(session_factory: sessionmaker[Session]) -> None:
    ack_data = json.loads((ROOT / "contracts/examples/command-ack.v1.json").read_text())
    envelope = CommandAckEnvelope.model_validate(ack_data)
    with session_factory() as session:
        session.add(
            DeviceCommand(
                command_id=str(envelope.command_id),
                device_id="motor-01",
                kind="set_demo_relay",
                parameters={"relay_on": False, "timeout_s": 10},
                status="published",
                issued_by="demo-admin",
                issued_at=envelope.device_time,
                expires_at=envelope.device_time,
            )
        )
        session.commit()
        result = persist_command_ack(session, envelope)
        command = session.get(DeviceCommand, str(envelope.command_id))

    assert result.status == "inserted"
    assert command is not None
    assert command.status == "completed"
    assert command.result_code == "RELAY_OFF"
