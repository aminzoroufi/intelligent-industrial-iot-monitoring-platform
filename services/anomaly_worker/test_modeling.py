# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from services.anomaly_worker.features import TelemetrySample, generate_features
from services.anomaly_worker.modeling import (
    ArtifactError,
    ModelBundle,
    TrainingError,
    load_bundle,
    model_is_stale,
    save_bundle,
    score_rows,
    train_model,
)
from simulator.telemetry_generator.main import scenario_values


def regime_samples(name: str, count: int, *, start_id: int = 0) -> list[TelemetrySample]:
    start = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=10 * start_id)
    return [
        TelemetrySample(
            sample_id=start_id + index,
            timestamp=start + timedelta(seconds=10 * index),
            temperature_c=float(values["temperature_c"]),
            vibration_rms_mps2=float(values["vibration_rms_mps2"]),
            vibration_peak_mps2=float(values["vibration_peak_mps2"]),
            vibration_crest_factor=float(values["vibration_crest_factor"]),
            current_a=float(values["current_a"]),
            quality=str(values["quality"]),
            fault_flags=tuple(str(value) for value in values["fault_flags"]),
            regime=name,
        )
        for index, values in enumerate(scenario_values(name, count))
    ]


def trained_bundle() -> tuple[list[TelemetrySample], ModelBundle]:
    healthy = regime_samples("normal", 360)
    bundle = train_model(
        healthy,
        device_id="motor-01",
        asset_class="dc-motor",
        baseline_start=healthy[0].timestamp,
        baseline_end=healthy[-1].timestamp,
        minimum_feature_rows=200,
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    return healthy, bundle


def test_training_gates_bad_quality_and_is_reproducible() -> None:
    healthy = regime_samples("normal", 360)
    first = train_model(
        healthy,
        device_id="motor-01",
        asset_class="dc-motor",
        baseline_start=healthy[0].timestamp,
        baseline_end=healthy[-1].timestamp,
        minimum_feature_rows=200,
    )
    second = train_model(
        healthy,
        device_id="motor-01",
        asset_class="dc-motor",
        baseline_start=healthy[0].timestamp,
        baseline_end=healthy[-1].timestamp,
        minimum_feature_rows=200,
    )
    rows = generate_features(healthy[-40:])
    assert np.allclose(
        [item.raw_anomaly_score for item in score_rows(first, rows)],
        [item.raw_anomaly_score for item in score_rows(second, rows)],
    )
    bad = regime_samples("sensor-stuck", 360)
    with pytest.raises(TrainingError, match="MODEL_NOT_READY"):
        train_model(
            bad,
            device_id="motor-01",
            asset_class="dc-motor",
            baseline_start=bad[0].timestamp,
            baseline_end=bad[-1].timestamp,
            minimum_feature_rows=300,
        )


def test_score_direction_percentile_and_reason_are_honest() -> None:
    healthy, bundle = trained_bundle()
    fault = regime_samples("vibration-imbalance", 40, start_id=len(healthy))
    rows = generate_features(healthy[-11:] + fault)
    results = score_rows(bundle, rows)
    assert results[-1].raw_anomaly_score > float(np.median(bundle.reference_scores))
    assert results[-1].empirical_percentile >= 95.0
    assert results[-1].anomalous
    assert "healthy 99th percentile" in results[-1].reason
    assert "probability" not in results[-1].reason


@pytest.mark.filterwarnings("ignore:Setting the shape on a NumPy array:DeprecationWarning")
def test_artifact_checksum_schema_and_staleness(tmp_path: Path) -> None:
    _, bundle = trained_bundle()
    directory, saved = save_bundle(bundle, tmp_path)
    loaded = load_bundle(directory)
    assert loaded.metadata.artifact_checksum == saved.metadata.artifact_checksum
    assert model_is_stale(
        loaded.metadata, now=datetime(2026, 3, 2, tzinfo=UTC), maximum_age_days=30
    )

    metadata_path = directory / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["feature_schema_version"] = 999
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ArtifactError, match="MODEL_FEATURE_SCHEMA_MISMATCH"):
        load_bundle(directory)
