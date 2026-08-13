# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""Database training and causal scoring orchestration for per-device models."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from services.anomaly_worker.features import TelemetrySample, generate_features
from services.anomaly_worker.modeling import (
    ArtifactError,
    ModelBundle,
    load_bundle,
    model_is_stale,
    save_bundle,
    score_rows,
    train_model,
)
from services.anomaly_worker.sensor_rules import SensorDiagnostic, detect_sensor_failures
from services.api.app.events import notify_after_commit
from services.api.app.models import Alarm, AnomalyModel, Device, ErrorLog, Telemetry, utc_now
from services.api.app.settings import Settings

MAX_BATCH_ROWS = 500
CONTEXT_ROWS = 12
DIAGNOSTIC_INTERVAL = timedelta(hours=1)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def telemetry_sample(row: Telemetry) -> TelemetrySample:
    return TelemetrySample(
        sample_id=row.id,
        timestamp=_aware(row.device_time or row.received_at),
        temperature_c=row.temperature_c,
        vibration_rms_mps2=row.vibration_rms_mps2,
        vibration_peak_mps2=row.vibration_peak_mps2,
        vibration_crest_factor=row.vibration_crest_factor,
        current_a=row.current_a,
        quality=row.quality,
        fault_flags=tuple(row.fault_flags),
    )


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _trusted_artifact_directory(model: AnomalyModel, root: Path) -> Path:
    resolved_root = root.resolve()
    candidate = (resolved_root / model.artifact_path).resolve()
    if not candidate.is_relative_to(resolved_root):
        raise ArtifactError("MODEL_ARTIFACT_PATH_INVALID")
    return candidate


def _register_bundle(
    session: Session, bundle: ModelBundle, directory: Path, root: Path
) -> AnomalyModel:
    metadata = bundle.metadata
    relative_path = str(directory.resolve().relative_to(root.resolve()))
    registry = session.scalar(
        select(AnomalyModel).where(
            AnomalyModel.device_id == metadata.device_id,
            AnomalyModel.model_version == metadata.model_version,
        )
    )
    if registry is None:
        registry = AnomalyModel(device_id=metadata.device_id, model_version=metadata.model_version)
        session.add(registry)
    registry.status = "ready"
    registry.feature_schema = {
        "version": metadata.feature_schema_version,
        "names": list(metadata.feature_names),
    }
    registry.training_start = _parse_utc(metadata.training_start)
    registry.training_end = _parse_utc(metadata.training_end)
    registry.training_sample_count = metadata.training_sample_count
    registry.validation_sample_count = metadata.validation_sample_count
    registry.contamination = metadata.contamination
    registry.random_seed = metadata.random_seed
    registry.sklearn_version = metadata.sklearn_version
    registry.artifact_path = relative_path
    registry.artifact_checksum = metadata.artifact_checksum
    registry.created_at = _parse_utc(metadata.created_at)
    registry.diagnostic = None
    session.commit()
    return registry


def train_and_register(
    session: Session,
    settings: Settings,
    *,
    device_id: str,
    baseline_start: datetime,
    baseline_end: datetime,
    contamination: float = 0.02,
) -> AnomalyModel:
    device = session.get(Device, device_id)
    if device is None:
        raise ValueError("DEVICE_NOT_FOUND")
    rows = list(
        session.scalars(
            select(Telemetry)
            .where(
                Telemetry.device_id == device_id,
                Telemetry.received_at >= baseline_start,
                Telemetry.received_at <= baseline_end,
            )
            .order_by(Telemetry.received_at, Telemetry.id)
        )
    )
    bundle = train_model(
        [telemetry_sample(row) for row in rows],
        device_id=device.id,
        asset_class=device.asset_class,
        baseline_start=baseline_start,
        baseline_end=baseline_end,
        minimum_feature_rows=settings.anomaly_minimum_feature_rows,
        contamination=contamination,
    )
    root = Path(settings.model_root)
    try:
        directory, saved = save_bundle(bundle, root)
    except FileExistsError:
        directory = root / device_id / bundle.metadata.model_version
        saved = load_bundle(directory)
        if saved.metadata.device_id != device_id or (
            saved.metadata.model_version != bundle.metadata.model_version
        ):
            raise ArtifactError("MODEL_EXISTING_ARTIFACT_MISMATCH") from None
    return _register_bundle(session, saved, directory, root)


def _latest_registry(session: Session, device_id: str) -> AnomalyModel | None:
    return session.scalar(
        select(AnomalyModel)
        .where(AnomalyModel.device_id == device_id)
        .order_by(AnomalyModel.created_at.desc(), AnomalyModel.id.desc())
        .limit(1)
    )


def _log_diagnostic(
    session: Session, *, device_id: str, code: str, severity: str, detail: str
) -> None:
    recent = session.scalar(
        select(ErrorLog.id)
        .where(
            ErrorLog.component == "anomaly-worker",
            ErrorLog.device_id == device_id,
            ErrorLog.error_code == code,
            ErrorLog.created_at >= utc_now() - DIAGNOSTIC_INTERVAL,
        )
        .limit(1)
    )
    if recent is None:
        session.add(
            ErrorLog(
                component="anomaly-worker",
                error_code=code,
                severity=severity,
                device_id=device_id,
                detail=detail[:300],
            )
        )


def _load_ready_bundle(
    session: Session, settings: Settings, device_id: str
) -> tuple[AnomalyModel | None, ModelBundle | None, str | None]:
    registry = _latest_registry(session, device_id)
    if registry is None:
        return None, None, "MODEL_NOT_READY"
    try:
        bundle = load_bundle(_trusted_artifact_directory(registry, Path(settings.model_root)))
        if bundle.metadata.device_id != device_id or (
            bundle.metadata.model_version != registry.model_version
        ):
            raise ArtifactError("MODEL_REGISTRY_MISMATCH")
        if bundle.metadata.artifact_checksum != registry.artifact_checksum:
            raise ArtifactError("MODEL_REGISTRY_CHECKSUM_MISMATCH")
        if model_is_stale(bundle.metadata, maximum_age_days=settings.model_stale_after_days):
            registry.status = "stale"
            registry.diagnostic = "MODEL_STALE: retraining is required"
            return registry, None, "MODEL_STALE"
    except (ArtifactError, OSError, ValueError) as exc:
        code = str(exc)[:48] or "MODEL_ARTIFACT_INVALID"
        registry.status = "error"
        registry.diagnostic = f"{code}: deterministic rules remain active"[:300]
        return registry, None, code
    registry.status = "ready"
    registry.diagnostic = None
    return registry, bundle, None


def _targets(session: Session, device_id: str, model_ready: bool) -> list[Telemetry]:
    query: Select[tuple[Telemetry]] = select(Telemetry).where(
        Telemetry.device_id == device_id,
        Telemetry.anomaly_score.is_(None),
    )
    if model_ready:
        query = query.where(
            or_(
                Telemetry.anomaly_reason.is_(None),
                ~Telemetry.anomaly_reason.startswith("FEATURE_WINDOW_NOT_READY"),
            )
        )
    else:
        query = query.where(Telemetry.anomaly_reason.is_(None))
    query = query.order_by(Telemetry.received_at, Telemetry.id).limit(MAX_BATCH_ROWS)
    return list(session.scalars(query))


def _context_rows(session: Session, device_id: str, targets: list[Telemetry]) -> list[Telemetry]:
    before = list(
        session.scalars(
            select(Telemetry)
            .where(
                Telemetry.device_id == device_id,
                Telemetry.received_at < targets[0].received_at,
            )
            .order_by(Telemetry.received_at.desc(), Telemetry.id.desc())
            .limit(CONTEXT_ROWS - 1)
        )
    )
    batch = list(
        session.scalars(
            select(Telemetry)
            .where(
                Telemetry.device_id == device_id,
                Telemetry.received_at >= targets[0].received_at,
                Telemetry.received_at <= targets[-1].received_at,
            )
            .order_by(Telemetry.received_at, Telemetry.id)
        )
    )
    return [*reversed(before), *batch]


def _diagnostic_reason(diagnostics: tuple[SensorDiagnostic, ...]) -> str:
    return "; ".join(f"{item.code}: {item.reason}" for item in diagnostics)[:300]


def _set_alarm(
    session: Session,
    *,
    device_id: str,
    code: str,
    source: str,
    active: bool,
    summary: str,
) -> None:
    alarm = session.scalar(
        select(Alarm).where(
            Alarm.device_id == device_id,
            Alarm.code == code,
            Alarm.source == source,
            Alarm.state == "active",
        )
    )
    if active and alarm is None:
        session.add(
            Alarm(
                device_id=device_id,
                code=code,
                severity="warning",
                source=source,
                state="active",
                summary=summary[:240],
            )
        )
    elif active and alarm is not None:
        alarm.summary = summary[:240]
    elif not active and alarm is not None:
        alarm.state = "cleared"
        alarm.cleared_at = utc_now()


def score_device_once(session: Session, settings: Settings, device_id: str) -> int:
    registry, bundle, model_error = _load_ready_bundle(session, settings, device_id)
    targets = _targets(session, device_id, bundle is not None)
    if not targets:
        session.commit()
        return 0
    context = _context_rows(session, device_id, targets)
    samples = [telemetry_sample(row) for row in context]
    target_ids = {row.id for row in targets}
    diagnostics_by_id: dict[int, tuple[SensorDiagnostic, ...]] = {}
    for index, sample in enumerate(samples):
        if sample.sample_id in target_ids:
            diagnostics_by_id[sample.sample_id] = detect_sensor_failures(
                samples[max(0, index - CONTEXT_ROWS + 1) : index + 1]
            )

    processed = 0
    anomaly_active = False
    latest_reason = "No model anomaly in the latest scored batch"
    if bundle is None:
        code = model_error or "MODEL_NOT_READY"
        detail = f"{code}: deterministic sensor and threshold rules remain active"
        _log_diagnostic(
            session,
            device_id=device_id,
            code=code,
            severity="warning" if code != "MODEL_NOT_READY" else "info",
            detail=detail,
        )
        for row in targets:
            diagnostics = diagnostics_by_id[row.id]
            row.anomaly_reason = _diagnostic_reason(diagnostics) if diagnostics else detail
            processed += 1
    else:
        results = {
            result.sample_id: result
            for result in score_rows(bundle, generate_features(samples))
            if result.sample_id in target_ids
        }
        for row in targets:
            result = results.get(row.id)
            diagnostics = diagnostics_by_id[row.id]
            if result is None:
                row.anomaly_reason = "FEATURE_WINDOW_NOT_READY: waiting for causal context"
                continue
            row.anomaly_score = result.raw_anomaly_score
            row.anomaly_percentile = result.empirical_percentile
            row.anomaly_reason = _diagnostic_reason(diagnostics) if diagnostics else result.reason
            processed += 1
            if row.id == targets[-1].id:
                anomaly_active = result.anomalous
                latest_reason = result.reason
        if registry is not None:
            registry.last_scored_at = utc_now()

    latest_target = targets[-1]
    latest_diagnostics = diagnostics_by_id[latest_target.id]
    _set_alarm(
        session,
        device_id=device_id,
        code="SENSOR_DIAGNOSTIC",
        source="sensor_rule",
        active=bool(latest_diagnostics),
        summary=_diagnostic_reason(latest_diagnostics) or "Sensor diagnostics cleared",
    )
    if bundle is not None:
        _set_alarm(
            session,
            device_id=device_id,
            code="ANOMALY_DETECTED",
            source="anomaly",
            active=anomaly_active,
            summary=f"Isolation Forest: {latest_reason}",
        )
    notify_after_commit(
        session,
        {
            "type": "anomaly_scoring",
            "device_id": device_id,
            "processed": processed,
            "model_version": registry.model_version if registry is not None else None,
            "model_status": registry.status if registry is not None else "model_not_ready",
        },
    )
    session.commit()
    return processed


def run_once(session: Session, settings: Settings) -> int:
    processed = 0
    for device_id in session.scalars(select(Device.id).order_by(Device.id)):
        processed += score_device_once(session, settings, device_id)
    return processed
