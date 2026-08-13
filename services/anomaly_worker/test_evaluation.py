# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
from __future__ import annotations

from datetime import UTC, datetime

from services.anomaly_worker.evaluation import evaluate_detectors
from services.anomaly_worker.modeling import train_model
from services.anomaly_worker.test_modeling import regime_samples


def test_evaluation_is_labeled_synthetic_and_reports_required_metrics() -> None:
    baseline = regime_samples("normal", 360)
    bundle = train_model(
        baseline,
        device_id="motor-01",
        asset_class="dc-motor",
        baseline_start=baseline[0].timestamp,
        baseline_end=baseline[-1].timestamp,
        minimum_feature_rows=200,
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    evaluation = []
    next_id = 10_000
    for name in (
        "normal",
        "rising-temperature",
        "vibration-imbalance",
        "current-overload",
        "sensor-stuck",
    ):
        values = regime_samples(name, 60, start_id=next_id)
        evaluation.extend(values)
        next_id += len(values) + 100
    report = evaluate_detectors(bundle, evaluation)
    assert report["data_kind"] == "synthetic"
    assert report["field_performance_claimed"] is False
    assert "not a probability" in str(report["score_interpretation"])
    for detector in ("deterministic_detector", "isolation_forest"):
        metrics = report[detector]
        assert isinstance(metrics, dict)
        assert {"precision", "recall", "f1", "false_positive_rate"} <= metrics.keys()
        assert (
            sum(
                int(metrics[name])
                for name in ("true_positive", "false_positive", "true_negative", "false_negative")
            )
            == 275
        )
    scenarios = report["scenarios"]
    assert isinstance(scenarios, list)
    assert {item["scenario"] for item in scenarios} == {
        "normal",
        "rising-temperature",
        "vibration-imbalance",
        "current-overload",
        "sensor-stuck",
    }
