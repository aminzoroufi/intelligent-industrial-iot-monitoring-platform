# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""Deterministic synthetic fixtures for reproducible detector evaluation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from services.anomaly_worker.features import TelemetrySample
from simulator.telemetry_generator.main import scenario_values


def scenario_samples(
    name: str,
    count: int,
    *,
    sample_id_start: int,
    start: datetime,
    seed: int = 20260811,
) -> list[TelemetrySample]:
    samples: list[TelemetrySample] = []
    for offset, values in enumerate(scenario_values(name, count, seed)):
        samples.append(
            TelemetrySample(
                sample_id=sample_id_start + offset,
                timestamp=start + timedelta(seconds=10 * offset),
                temperature_c=float(values["temperature_c"]),
                vibration_rms_mps2=float(values["vibration_rms_mps2"]),
                vibration_peak_mps2=float(values["vibration_peak_mps2"]),
                vibration_crest_factor=float(values["vibration_crest_factor"]),
                current_a=float(values["current_a"]),
                quality=str(values["quality"]),
                fault_flags=tuple(str(item) for item in values["fault_flags"]),
                regime=name,
            )
        )
    return samples


def demo_training_samples() -> list[TelemetrySample]:
    return scenario_samples(
        "normal",
        360,
        sample_id_start=1,
        start=datetime(2026, 8, 1, 8, 0, tzinfo=UTC),
    )


def demo_evaluation_samples() -> list[TelemetrySample]:
    scenarios = (
        "normal",
        "rising-temperature",
        "vibration-imbalance",
        "current-overload",
        "sensor-stuck",
    )
    samples: list[TelemetrySample] = []
    for index, name in enumerate(scenarios):
        samples.extend(
            scenario_samples(
                name,
                60,
                sample_id_start=10_000 + index * 1_000,
                start=datetime(2026, 8, 2 + index, 8, 0, tzinfo=UTC),
                seed=20260811 + index,
            )
        )
    return samples
