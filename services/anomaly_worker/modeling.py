# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""Reproducible Isolation Forest training, scoring, and trusted artifact handling."""

from __future__ import annotations

import hashlib
import json
import os
import pickle
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import joblib  # type: ignore[import-untyped]
import numpy as np
import numpy.typing as npt
import sklearn  # type: ignore[import-untyped]
from sklearn.ensemble import IsolationForest  # type: ignore[import-untyped]

from services.anomaly_worker.features import (
    FEATURE_NAMES,
    FEATURE_SCHEMA_VERSION,
    FeatureRow,
    TelemetrySample,
    feature_matrix,
    generate_features,
)

DEFAULT_RANDOM_SEED = 20260811
ARTIFACT_FILENAME = "model.joblib"
METADATA_FILENAME = "metadata.json"


class TrainingError(ValueError):
    """The selected baseline did not satisfy an explicit training gate."""


class ArtifactError(ValueError):
    """A model artifact failed integrity or compatibility checks."""


@dataclass(frozen=True)
class ModelMetadata:
    device_id: str
    asset_class: str
    model_version: str
    feature_schema_version: int
    feature_names: tuple[str, ...]
    training_start: str
    training_end: str
    training_sample_count: int
    validation_sample_count: int
    contamination: float
    random_seed: int
    sklearn_version: str
    created_at: str
    score_direction: str
    baseline_policy: str
    artifact_checksum: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ModelMetadata:
        try:
            metadata = cls(
                device_id=str(value["device_id"]),
                asset_class=str(value["asset_class"]),
                model_version=str(value["model_version"]),
                feature_schema_version=int(value["feature_schema_version"]),
                feature_names=tuple(str(item) for item in value["feature_names"]),
                training_start=str(value["training_start"]),
                training_end=str(value["training_end"]),
                training_sample_count=int(value["training_sample_count"]),
                validation_sample_count=int(value["validation_sample_count"]),
                contamination=float(value["contamination"]),
                random_seed=int(value["random_seed"]),
                sklearn_version=str(value["sklearn_version"]),
                created_at=str(value["created_at"]),
                score_direction=str(value["score_direction"]),
                baseline_policy=str(value["baseline_policy"]),
                artifact_checksum=str(value["artifact_checksum"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ArtifactError("MODEL_METADATA_INVALID") from exc
        if (
            not metadata.device_id
            or not metadata.model_version
            or metadata.training_sample_count < 1
            or metadata.validation_sample_count < 20
            or not 0.001 <= metadata.contamination <= 0.2
            or not metadata.artifact_checksum.startswith("sha256:")
        ):
            raise ArtifactError("MODEL_METADATA_INVALID")
        return metadata


@dataclass(frozen=True)
class ModelBundle:
    estimator: IsolationForest
    reference_scores: npt.NDArray[np.float64]
    feature_quantiles: dict[str, tuple[float, float, float]]
    metadata: ModelMetadata


@dataclass(frozen=True)
class ScoreResult:
    sample_id: int
    raw_anomaly_score: float
    empirical_percentile: float
    anomalous: bool
    reason: str


def _isoformat(value: datetime) -> str:
    if value.tzinfo is None:
        raise TrainingError("TRAINING_WINDOW_MUST_BE_TIMEZONE_AWARE")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _model_version(
    device_id: str, start: datetime, end: datetime, contamination: float, random_seed: int
) -> str:
    value = (
        f"{device_id}|{_isoformat(start)}|{_isoformat(end)}|{FEATURE_SCHEMA_VERSION}|"
        f"{contamination:.8g}|{random_seed}"
    )
    return f"iforest-v1-{hashlib.sha256(value.encode()).hexdigest()[:12]}"


def train_model(
    samples: list[TelemetrySample],
    *,
    device_id: str,
    asset_class: str,
    baseline_start: datetime,
    baseline_end: datetime,
    minimum_feature_rows: int = 200,
    contamination: float = 0.02,
    random_seed: int = DEFAULT_RANDOM_SEED,
    created_at: datetime | None = None,
) -> ModelBundle:
    if baseline_start >= baseline_end:
        raise TrainingError("TRAINING_WINDOW_INVALID")
    if not 0.001 <= contamination <= 0.2:
        raise TrainingError("CONTAMINATION_OUT_OF_RANGE")
    selected = [item for item in samples if baseline_start <= item.timestamp <= baseline_end]
    rows = generate_features(selected, healthy_windows_only=True)
    if len(rows) < minimum_feature_rows:
        raise TrainingError(
            f"MODEL_NOT_READY: {len(rows)} healthy feature rows; minimum is {minimum_feature_rows}"
        )
    split = max(int(len(rows) * 0.8), minimum_feature_rows * 3 // 4)
    if len(rows) - split < max(20, minimum_feature_rows // 10):
        raise TrainingError("MODEL_NOT_READY: healthy validation split is too small")
    training_matrix = feature_matrix(rows[:split])
    validation_matrix = feature_matrix(rows[split:])
    estimator = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=random_seed,
        n_jobs=1,
    )
    estimator.fit(training_matrix)
    reference_scores = -estimator.score_samples(validation_matrix)
    quantiles: dict[str, tuple[float, float, float]] = {}
    for index, name in enumerate(FEATURE_NAMES):
        low, median, high = np.quantile(training_matrix[:, index], [0.01, 0.5, 0.99])
        quantiles[name] = (float(low), float(median), float(high))
    now = created_at or datetime.now(UTC)
    metadata = ModelMetadata(
        device_id=device_id,
        asset_class=asset_class,
        model_version=_model_version(
            device_id, baseline_start, baseline_end, contamination, random_seed
        ),
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        feature_names=FEATURE_NAMES,
        training_start=_isoformat(baseline_start),
        training_end=_isoformat(baseline_end),
        training_sample_count=len(training_matrix),
        validation_sample_count=len(validation_matrix),
        contamination=contamination,
        random_seed=random_seed,
        sklearn_version=sklearn.__version__,
        created_at=_isoformat(now),
        score_direction="higher_is_more_anomalous; not a probability",
        baseline_policy="quality=good, no fault flags, causal healthy-only rolling windows",
        artifact_checksum="",
    )
    return ModelBundle(
        estimator=estimator,
        reference_scores=np.asarray(reference_scores, dtype=np.float64),
        feature_quantiles=quantiles,
        metadata=metadata,
    )


def _percentile(reference: npt.NDArray[np.float64], score: float) -> float:
    ordered = np.sort(reference)
    return float(np.searchsorted(ordered, score, side="right") / len(ordered) * 100.0)


_FEATURE_LABELS = {
    "temperature_level_c": ("temperature level", "°C"),
    "temperature_slope_c_per_min": ("temperature slope", "°C/min"),
    "temperature_std_c": ("temperature variation", "°C"),
    "current_mean_a": ("current mean", "A"),
    "current_std_a": ("current variation", "A"),
    "vibration_rms_mean_mps2": ("vibration RMS", "m/s²"),
    "vibration_peak_max_mps2": ("vibration peak", "m/s²"),
    "vibration_crest_mean": ("crest factor", "ratio"),
    "vibration_to_current_ratio": ("vibration/current ratio", "m/s²/A"),
}


def _reason(row: FeatureRow, bundle: ModelBundle, anomalous: bool) -> str:
    evidence: list[tuple[float, str]] = []
    for index, name in enumerate(FEATURE_NAMES):
        value = row.values[index]
        low, median, high = bundle.feature_quantiles[name]
        span = max(high - low, abs(median) * 0.05, 1e-6)
        label, unit = _FEATURE_LABELS[name]
        if value > high:
            evidence.append(
                (
                    (value - high) / span,
                    f"{label} {value:.3g} {unit} is above its healthy 99th percentile "
                    f"{high:.3g} {unit}",
                )
            )
        elif value < low:
            evidence.append(
                (
                    (low - value) / span,
                    f"{label} {value:.3g} {unit} is below its healthy 1st percentile "
                    f"{low:.3g} {unit}",
                )
            )
    if evidence:
        return "; ".join(item[1] for item in sorted(evidence, reverse=True)[:2])[:300]
    if anomalous:
        return "multivariate feature combination is outside the healthy model region"
    return "features remain within the healthy validation-score distribution"


def score_rows(bundle: ModelBundle, rows: list[FeatureRow]) -> list[ScoreResult]:
    if bundle.metadata.feature_schema_version != FEATURE_SCHEMA_VERSION or (
        bundle.metadata.feature_names != FEATURE_NAMES
    ):
        raise ArtifactError("MODEL_FEATURE_SCHEMA_MISMATCH")
    matrix = feature_matrix(rows)
    if len(matrix) == 0:
        return []
    raw_scores = -bundle.estimator.score_samples(matrix)
    predictions = bundle.estimator.predict(matrix)
    results: list[ScoreResult] = []
    for row, score, prediction in zip(rows, raw_scores, predictions, strict=True):
        percentile = _percentile(bundle.reference_scores, float(score))
        anomalous = bool(prediction == -1 or percentile >= 99.0)
        results.append(
            ScoreResult(
                sample_id=row.sample_id,
                raw_anomaly_score=float(score),
                empirical_percentile=percentile,
                anomalous=anomalous,
                reason=_reason(row, bundle, anomalous),
            )
        )
    return results


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def save_bundle(bundle: ModelBundle, root: Path) -> tuple[Path, ModelBundle]:
    directory = root / bundle.metadata.device_id / bundle.metadata.model_version
    directory.mkdir(parents=True, exist_ok=False)
    artifact = directory / ARTIFACT_FILENAME
    artifact_temporary = directory / f"{ARTIFACT_FILENAME}.tmp"
    payload = {
        "estimator": bundle.estimator,
        "reference_scores": bundle.reference_scores,
        "feature_quantiles": bundle.feature_quantiles,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "feature_names": FEATURE_NAMES,
    }
    joblib.dump(payload, artifact_temporary, compress=3)
    os.replace(artifact_temporary, artifact)
    metadata = replace(bundle.metadata, artifact_checksum=f"sha256:{_checksum(artifact)}")
    metadata_path = directory / METADATA_FILENAME
    metadata_temporary = directory / f"{METADATA_FILENAME}.tmp"
    metadata_temporary.write_text(
        json.dumps(asdict(metadata), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(metadata_temporary, metadata_path)
    return directory, replace(bundle, metadata=metadata)


def load_bundle(directory: Path) -> ModelBundle:
    metadata_path = directory / METADATA_FILENAME
    artifact = directory / ARTIFACT_FILENAME
    try:
        raw_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactError("MODEL_METADATA_UNREADABLE") from exc
    if not isinstance(raw_metadata, dict):
        raise ArtifactError("MODEL_METADATA_INVALID")
    metadata = ModelMetadata.from_dict(raw_metadata)
    if metadata.feature_schema_version != FEATURE_SCHEMA_VERSION or (
        metadata.feature_names != FEATURE_NAMES
    ):
        raise ArtifactError("MODEL_FEATURE_SCHEMA_MISMATCH")
    if metadata.sklearn_version != sklearn.__version__:
        raise ArtifactError("MODEL_LIBRARY_VERSION_MISMATCH")
    try:
        checksum = f"sha256:{_checksum(artifact)}"
    except OSError as exc:
        raise ArtifactError("MODEL_ARTIFACT_UNREADABLE") from exc
    if checksum != metadata.artifact_checksum:
        raise ArtifactError("MODEL_ARTIFACT_CHECKSUM_MISMATCH")
    # joblib/pickle is loaded only after a trusted local artifact passes its recorded checksum.
    try:
        payload = joblib.load(artifact)
        estimator = payload["estimator"]
        reference_scores = np.asarray(payload["reference_scores"], dtype=np.float64)
        quantiles = payload["feature_quantiles"]
    except (
        OSError,
        KeyError,
        TypeError,
        ValueError,
        EOFError,
        AttributeError,
        ImportError,
        pickle.UnpicklingError,
    ) as exc:
        raise ArtifactError("MODEL_ARTIFACT_INVALID") from exc
    if (
        not isinstance(estimator, IsolationForest)
        or reference_scores.size < 20
        or not isinstance(quantiles, dict)
    ):
        raise ArtifactError("MODEL_ARTIFACT_INVALID")
    if not np.all(np.isfinite(reference_scores)) or set(quantiles) != set(FEATURE_NAMES):
        raise ArtifactError("MODEL_ARTIFACT_INVALID")
    parsed_quantiles: dict[str, tuple[float, float, float]] = {}
    for name, values in quantiles.items():
        parsed = tuple(float(value) for value in values)
        if len(parsed) != 3 or not all(np.isfinite(value) for value in parsed):
            raise ArtifactError("MODEL_ARTIFACT_INVALID")
        parsed_quantiles[str(name)] = (parsed[0], parsed[1], parsed[2])
    return ModelBundle(
        estimator=estimator,
        reference_scores=reference_scores,
        feature_quantiles=parsed_quantiles,
        metadata=metadata,
    )


def model_is_stale(
    metadata: ModelMetadata, *, now: datetime | None = None, maximum_age_days: int = 30
) -> bool:
    created = datetime.fromisoformat(metadata.created_at.replace("Z", "+00:00"))
    reference = now or datetime.now(UTC)
    return reference.astimezone(UTC) - created.astimezone(UTC) > timedelta(days=maximum_age_days)
