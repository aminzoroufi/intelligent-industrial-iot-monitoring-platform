# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from services.anomaly_worker.worker import run_once, train_and_register
from services.api.app.models import Alarm, AnomalyModel, Telemetry
from services.api.app.settings import Settings
from simulator.telemetry_generator.main import scenario_values

pytestmark = pytest.mark.filterwarnings(
    "ignore:Setting the shape on a NumPy array has been deprecated:DeprecationWarning:joblib"
)


def _settings(model_root: Path) -> Settings:
    return Settings(
        jwt_secret=SecretStr("test-jwt-secret-with-at-least-32-characters"),
        ingest_token=SecretStr("test-ingest-token-with-at-least-32-characters"),
        demo_admin_password=SecretStr("local-test-password"),
        model_root=str(model_root),
        anomaly_minimum_feature_rows=50,
    )


def _telemetry(sequence: int, timestamp: datetime, values: dict[str, Any]) -> Telemetry:
    return Telemetry(
        message_id=f"00000000-0000-4000-8000-{sequence:012d}",
        device_id="motor-01",
        site_id="workshop-demo",
        sequence=sequence,
        device_time=timestamp,
        received_at=timestamp,
        clock_synchronized=True,
        uptime_ms=sequence * 10_000,
        firmware_version="test",
        quality=str(values["quality"]),
        replayed=False,
        temperature_c=float(values["temperature_c"]),
        vibration_rms_mps2=float(values["vibration_rms_mps2"]),
        vibration_peak_mps2=float(values["vibration_peak_mps2"]),
        vibration_crest_factor=float(values["vibration_crest_factor"]),
        current_a=float(values["current_a"]),
        sample_quality={},
        fault_flags=[str(item) for item in values["fault_flags"]],
    )


def test_training_registry_scoring_and_sensor_fallback(
    session_factory: sessionmaker[Session], tmp_path: Path
) -> None:
    settings = _settings(tmp_path / "models")
    start = datetime(2026, 8, 10, 8, 0, tzinfo=UTC)
    normal_values = list(scenario_values("normal", 150))
    with session_factory() as session:
        for offset, values in enumerate(normal_values):
            session.add(_telemetry(offset + 1, start + timedelta(seconds=10 * offset), values))
        session.commit()
        registry = train_and_register(
            session,
            settings,
            device_id="motor-01",
            baseline_start=start,
            baseline_end=start + timedelta(seconds=1490),
        )
        assert registry.status == "ready"
        assert registry.artifact_checksum.startswith("sha256:")

        fault_start = start + timedelta(seconds=1500)
        for offset, values in enumerate(scenario_values("sensor-stuck", 12)):
            session.add(
                _telemetry(
                    151 + offset,
                    fault_start + timedelta(seconds=10 * offset),
                    values,
                )
            )
        session.commit()

        processed = run_once(session, settings)
        scored = session.scalar(
            select(func.count()).select_from(Telemetry).where(Telemetry.anomaly_score.is_not(None))
        )
        latest = session.scalar(select(Telemetry).order_by(Telemetry.id.desc()).limit(1))
        model = session.scalar(select(AnomalyModel).limit(1))
        sensor_alarm = session.scalar(
            select(Alarm).where(Alarm.code == "SENSOR_DIAGNOSTIC", Alarm.state == "active")
        )

        assert processed >= 150
        assert scored is not None and scored >= 150
        assert latest is not None and "SENSOR_STUCK" in str(latest.anomaly_reason)
        assert model is not None and model.last_scored_at is not None
        assert sensor_alarm is not None and sensor_alarm.source == "sensor_rule"
