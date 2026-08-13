# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""Authoritative sensor-failure rules independent of the statistical model."""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from services.anomaly_worker.features import TelemetrySample


@dataclass(frozen=True)
class SensorDiagnostic:
    code: str
    metric: str
    reason: str


def _diagnostic(code: str, metric: str, reason: str) -> SensorDiagnostic:
    return SensorDiagnostic(code=code, metric=metric, reason=reason)


def detect_sensor_failures(
    history: list[TelemetrySample], *, maximum_gap_s: float = 30.0
) -> tuple[SensorDiagnostic, ...]:
    if not history:
        return (_diagnostic("SAMPLES_MISSING", "all", "no telemetry samples are available"),)
    ordered = sorted(history, key=lambda item: (item.timestamp, item.sample_id))
    current = ordered[-1]
    diagnostics: list[SensorDiagnostic] = []
    if len(ordered) >= 2:
        gap_s = (current.timestamp - ordered[-2].timestamp).total_seconds()
        if gap_s > maximum_gap_s:
            diagnostics.append(
                _diagnostic(
                    "SAMPLES_MISSING",
                    "all",
                    f"sample gap is {gap_s:.1f} s, above the {maximum_gap_s:.1f} s limit",
                )
            )

    bounds = {
        "temperature": (current.temperature_c, -80.0, 200.0, "°C"),
        "current": (current.current_a, -0.1, 10.0, "A"),
        "vibration_rms": (current.vibration_rms_mps2, 0.0, 2000.0, "m/s²"),
        "vibration_peak": (current.vibration_peak_mps2, 0.0, 4000.0, "m/s²"),
        "crest_factor": (current.vibration_crest_factor, 0.0, 100.0, "ratio"),
    }
    for metric, (value, minimum, maximum, unit) in bounds.items():
        if value is None:
            diagnostics.append(_diagnostic("SENSOR_MISSING", metric, f"{metric} sample is missing"))
        elif value < minimum or value > maximum:
            diagnostics.append(
                _diagnostic(
                    "SENSOR_IMPOSSIBLE_RANGE",
                    metric,
                    f"{metric} is {value:.3g} {unit}, outside [{minimum:g}, {maximum:g}]",
                )
            )
    if (
        current.vibration_peak_mps2 is not None
        and current.vibration_rms_mps2 is not None
        and current.vibration_peak_mps2 + 1e-9 < current.vibration_rms_mps2
    ):
        diagnostics.append(
            _diagnostic(
                "SENSOR_RELATION_INVALID",
                "vibration",
                "vibration peak is below vibration RMS for the same aggregation window",
            )
        )

    recent = ordered[-12:]
    if len(recent) >= 8:
        sequences = {
            "temperature": [item.temperature_c for item in recent],
            "current": [item.current_a for item in recent],
            "vibration_rms": [item.vibration_rms_mps2 for item in recent],
        }
        stuck_tolerances = {"temperature": 0.001, "current": 0.0001, "vibration_rms": 0.0001}
        noise_limits = {"temperature": 5.0, "current": 0.8, "vibration_rms": 12.0}
        for metric, nullable_values in sequences.items():
            if any(value is None for value in nullable_values):
                continue
            values = [float(value) for value in nullable_values if value is not None]
            if max(values) - min(values) <= stuck_tolerances[metric]:
                diagnostics.append(
                    _diagnostic(
                        "SENSOR_STUCK",
                        metric,
                        f"{metric} changed by no more than {stuck_tolerances[metric]:g} "
                        f"across {len(values)} samples",
                    )
                )
            elif statistics.pstdev(values) > noise_limits[metric]:
                diagnostics.append(
                    _diagnostic(
                        "SENSOR_EXCESSIVE_NOISE",
                        metric,
                        f"{metric} standard deviation is {statistics.pstdev(values):.3g}, "
                        f"above {noise_limits[metric]:g}",
                    )
                )

    if len(ordered) >= 2:
        previous = ordered[-2]
        elapsed_s = max((current.timestamp - previous.timestamp).total_seconds(), 1e-6)
        rates = {
            "temperature": (previous.temperature_c, current.temperature_c, 10.0, "°C/s"),
            "current": (previous.current_a, current.current_a, 3.0, "A/s"),
            "vibration_rms": (
                previous.vibration_rms_mps2,
                current.vibration_rms_mps2,
                100.0,
                "m/s²/s",
            ),
        }
        for metric, (before, after, limit, unit) in rates.items():
            if before is None or after is None:
                continue
            rate = abs(after - before) / elapsed_s
            if rate > limit:
                diagnostics.append(
                    _diagnostic(
                        "SENSOR_RATE_INVALID",
                        metric,
                        f"{metric} rate is {rate:.3g} {unit}, above {limit:g}",
                    )
                )

    unique: dict[tuple[str, str], SensorDiagnostic] = {}
    for item in diagnostics:
        unique.setdefault((item.code, item.metric), item)
    return tuple(unique.values())
