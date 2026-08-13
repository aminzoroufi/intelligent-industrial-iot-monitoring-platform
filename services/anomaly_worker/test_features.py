# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from services.anomaly_worker.features import TelemetrySample, generate_features
from services.anomaly_worker.sensor_rules import detect_sensor_failures


def samples(count: int = 20) -> list[TelemetrySample]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        TelemetrySample(
            sample_id=index,
            timestamp=start + timedelta(seconds=10 * index),
            temperature_c=40.0 + 0.05 * index,
            vibration_rms_mps2=1.0 + 0.01 * index,
            vibration_peak_mps2=2.2 + 0.02 * index,
            vibration_crest_factor=2.2,
            current_a=0.6 + 0.001 * index,
            regime="normal",
        )
        for index in range(count)
    ]


def test_features_are_causal_and_have_explicit_units() -> None:
    original = samples()
    before = generate_features(original)
    changed = original.copy()
    changed[-1] = replace(changed[-1], temperature_c=150.0)
    after = generate_features(changed)
    assert [row.values for row in before[:-1]] == [row.values for row in after[:-1]]
    assert before[-1].values[1] == pytest.approx(0.3, rel=0.05)


def test_feature_windows_do_not_bridge_large_gaps_or_fault_rows_for_training() -> None:
    values = samples(14)
    values[7] = replace(values[7], timestamp=values[6].timestamp + timedelta(minutes=5))
    for index in range(8, len(values)):
        values[index] = replace(
            values[index], timestamp=values[7].timestamp + timedelta(seconds=10 * (index - 7))
        )
    rows = generate_features(values, maximum_gap_s=30.0)
    assert all(row.sample_id <= 6 or row.sample_id >= 12 for row in rows)
    faulty = values.copy()
    faulty[-1] = replace(faulty[-1], fault_flags=("SYNTHETIC_FAULT",))
    healthy_rows = generate_features(faulty, healthy_windows_only=True)
    assert all(row.sample_id != faulty[-1].sample_id for row in healthy_rows)


def test_sensor_rules_cover_missing_stuck_range_noise_and_rate() -> None:
    base = samples(12)
    stuck = [replace(item, temperature_c=41.0) for item in base]
    assert any(item.code == "SENSOR_STUCK" for item in detect_sensor_failures(stuck))

    impossible = base.copy()
    impossible[-1] = replace(impossible[-1], current_a=12.0)
    assert any(
        item.code == "SENSOR_IMPOSSIBLE_RANGE" for item in detect_sensor_failures(impossible)
    )

    noisy = [
        replace(item, vibration_rms_mps2=1.0 if index % 2 else 40.0)
        for index, item in enumerate(base)
    ]
    assert any(item.code == "SENSOR_EXCESSIVE_NOISE" for item in detect_sensor_failures(noisy))

    missing = base.copy()
    missing[-1] = replace(
        missing[-1], timestamp=missing[-2].timestamp + timedelta(minutes=2), temperature_c=None
    )
    codes = {item.code for item in detect_sensor_failures(missing)}
    assert {"SAMPLES_MISSING", "SENSOR_MISSING"} <= codes

    rate = base.copy()
    rate[-1] = replace(rate[-1], temperature_c=190.0)
    assert any(item.code == "SENSOR_RATE_INVALID" for item in detect_sensor_failures(rate))
