# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""Causal rolling features for condition telemetry."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import numpy.typing as npt

FEATURE_SCHEMA_VERSION = 1
FEATURE_NAMES = (
    "temperature_level_c",
    "temperature_slope_c_per_min",
    "temperature_std_c",
    "current_mean_a",
    "current_std_a",
    "vibration_rms_mean_mps2",
    "vibration_peak_max_mps2",
    "vibration_crest_mean",
    "vibration_to_current_ratio",
)


@dataclass(frozen=True)
class TelemetrySample:
    sample_id: int
    timestamp: datetime
    temperature_c: float | None
    vibration_rms_mps2: float | None
    vibration_peak_mps2: float | None
    vibration_crest_factor: float | None
    current_a: float | None
    quality: str = "good"
    fault_flags: tuple[str, ...] = ()
    regime: str = "unknown"

    @property
    def measurements_are_finite(self) -> bool:
        values = (
            self.temperature_c,
            self.vibration_rms_mps2,
            self.vibration_peak_mps2,
            self.vibration_crest_factor,
            self.current_a,
        )
        return all(value is not None and math.isfinite(value) for value in values)

    @property
    def is_healthy(self) -> bool:
        return self.quality == "good" and not self.fault_flags and self.measurements_are_finite


@dataclass(frozen=True)
class FeatureRow:
    sample_id: int
    timestamp: datetime
    regime: str
    values: tuple[float, ...]

    def array(self) -> npt.NDArray[np.float64]:
        return np.asarray(self.values, dtype=np.float64)


def _slope_per_minute(times_s: npt.NDArray[np.float64], values: npt.NDArray[np.float64]) -> float:
    centered = times_s - times_s.mean()
    denominator = float(np.dot(centered, centered))
    if denominator <= 0.0:
        return 0.0
    return float(np.dot(centered, values - values.mean()) / denominator * 60.0)


def generate_features(
    samples: list[TelemetrySample],
    *,
    window_size: int = 12,
    minimum_window: int = 6,
    maximum_gap_s: float = 30.0,
    healthy_windows_only: bool = False,
) -> list[FeatureRow]:
    if window_size < minimum_window or minimum_window < 2:
        raise ValueError("window_size must be at least minimum_window >= 2")
    ordered = sorted(samples, key=lambda item: (item.timestamp, item.sample_id))
    rows: list[FeatureRow] = []
    segment: list[TelemetrySample] = []
    previous_time: datetime | None = None
    for sample in ordered:
        if (
            previous_time is not None
            and (sample.timestamp - previous_time).total_seconds() > maximum_gap_s
        ):
            segment.clear()
        previous_time = sample.timestamp
        segment.append(sample)
        if len(segment) > window_size:
            segment.pop(0)
        if len(segment) < minimum_window or not all(
            item.measurements_are_finite for item in segment
        ):
            continue
        if healthy_windows_only and not all(item.is_healthy for item in segment):
            continue
        first_time = segment[0].timestamp
        times = np.asarray(
            [(item.timestamp - first_time).total_seconds() for item in segment],
            dtype=np.float64,
        )
        temperature = np.asarray([item.temperature_c for item in segment], dtype=np.float64)
        current = np.asarray([item.current_a for item in segment], dtype=np.float64)
        vibration_rms = np.asarray([item.vibration_rms_mps2 for item in segment], dtype=np.float64)
        vibration_peak = np.asarray(
            [item.vibration_peak_mps2 for item in segment], dtype=np.float64
        )
        crest = np.asarray([item.vibration_crest_factor for item in segment], dtype=np.float64)
        current_mean = float(current.mean())
        values = (
            float(temperature[-1]),
            _slope_per_minute(times, temperature),
            float(temperature.std()),
            current_mean,
            float(current.std()),
            float(vibration_rms.mean()),
            float(vibration_peak.max()),
            float(crest.mean()),
            float(vibration_rms.mean() / max(abs(current_mean), 0.05)),
        )
        if all(math.isfinite(value) for value in values):
            rows.append(
                FeatureRow(
                    sample_id=sample.sample_id,
                    timestamp=sample.timestamp,
                    regime=sample.regime,
                    values=values,
                )
            )
    return rows


def feature_matrix(rows: list[FeatureRow]) -> npt.NDArray[np.float64]:
    if not rows:
        return np.empty((0, len(FEATURE_NAMES)), dtype=np.float64)
    return np.vstack([row.array() for row in rows])
