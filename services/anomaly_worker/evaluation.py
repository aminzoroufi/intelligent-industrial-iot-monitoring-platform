# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""Synthetic, explicitly labeled threshold-versus-model evaluation."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from services.anomaly_worker.features import TelemetrySample, generate_features
from services.anomaly_worker.modeling import ModelBundle, score_rows
from services.anomaly_worker.sensor_rules import detect_sensor_failures


@dataclass(frozen=True)
class DetectorMetrics:
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int
    precision: float
    recall: float
    f1: float
    false_positive_rate: float


@dataclass(frozen=True)
class ScenarioOutcome:
    scenario: str
    evaluated_samples: int
    first_deterministic_detection_delay_s: float | None
    first_model_detection_delay_s: float | None


def _metrics(truth: list[bool], predictions: list[bool]) -> DetectorMetrics:
    true_positive = sum(
        expected and actual for expected, actual in zip(truth, predictions, strict=True)
    )
    false_positive = sum(
        not expected and actual for expected, actual in zip(truth, predictions, strict=True)
    )
    true_negative = sum(
        not expected and not actual for expected, actual in zip(truth, predictions, strict=True)
    )
    false_negative = sum(
        expected and not actual for expected, actual in zip(truth, predictions, strict=True)
    )
    precision = true_positive / max(true_positive + false_positive, 1)
    recall = true_positive / max(true_positive + false_negative, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-12)
    false_positive_rate = false_positive / max(false_positive + true_negative, 1)
    return DetectorMetrics(
        true_positive=true_positive,
        false_positive=false_positive,
        true_negative=true_negative,
        false_negative=false_negative,
        precision=precision,
        recall=recall,
        f1=f1,
        false_positive_rate=false_positive_rate,
    )


def _threshold_or_sensor_rule(history: list[TelemetrySample]) -> bool:
    current = history[-1]
    threshold = (
        (current.temperature_c is not None and current.temperature_c >= 65.0)
        or (current.vibration_rms_mps2 is not None and current.vibration_rms_mps2 >= 4.5)
        or (current.current_a is not None and current.current_a >= 1.4)
    )
    return threshold or bool(detect_sensor_failures(history[-12:]))


def _delay(
    samples: list[TelemetrySample], ids: list[int], predictions: dict[int, bool]
) -> float | None:
    if not ids:
        return None
    by_id = {sample.sample_id: sample for sample in samples}
    start = by_id[ids[0]].timestamp
    for sample_id in ids:
        if predictions.get(sample_id, False):
            return (by_id[sample_id].timestamp - start).total_seconds()
    return None


def evaluate_detectors(bundle: ModelBundle, samples: list[TelemetrySample]) -> dict[str, object]:
    grouped: dict[str, list[TelemetrySample]] = {}
    for sample in sorted(samples, key=lambda item: (item.timestamp, item.sample_id)):
        grouped.setdefault(sample.regime, []).append(sample)

    truth: list[bool] = []
    deterministic_predictions: list[bool] = []
    model_predictions: list[bool] = []
    outcomes: list[ScenarioOutcome] = []
    reasons: dict[str, list[str]] = {}
    for regime, regime_samples in grouped.items():
        rows = generate_features(regime_samples)
        scores = {result.sample_id: result for result in score_rows(bundle, rows)}
        row_ids = [row.sample_id for row in rows]
        deterministic_by_id: dict[int, bool] = {}
        model_by_id: dict[int, bool] = {}
        for index, sample in enumerate(regime_samples):
            if sample.sample_id not in scores:
                continue
            expected = regime != "normal"
            deterministic = _threshold_or_sensor_rule(regime_samples[: index + 1])
            model = scores[sample.sample_id].anomalous
            truth.append(expected)
            deterministic_predictions.append(deterministic)
            model_predictions.append(model)
            deterministic_by_id[sample.sample_id] = deterministic
            model_by_id[sample.sample_id] = model
            if model:
                reasons.setdefault(regime, []).append(scores[sample.sample_id].reason)
        outcomes.append(
            ScenarioOutcome(
                scenario=regime,
                evaluated_samples=len(row_ids),
                first_deterministic_detection_delay_s=_delay(
                    regime_samples, row_ids, deterministic_by_id
                ),
                first_model_detection_delay_s=_delay(regime_samples, row_ids, model_by_id),
            )
        )
    return {
        "schema_version": 1,
        "data_kind": "synthetic",
        "field_performance_claimed": False,
        "model_version": bundle.metadata.model_version,
        "score_interpretation": bundle.metadata.score_direction,
        "deterministic_detector": asdict(_metrics(truth, deterministic_predictions)),
        "isolation_forest": asdict(_metrics(truth, model_predictions)),
        "scenarios": [asdict(item) for item in outcomes],
        "example_model_reasons": {
            regime: list(dict.fromkeys(values))[:3] for regime, values in reasons.items()
        },
    }


def write_evaluation(report: dict[str, object], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, output)
