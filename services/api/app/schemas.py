# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""Validated API and device-contract models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - OAuth token type, not a secret
    expires_in_s: int


class UserView(BaseModel):
    username: str
    role: str


class SensorQuality(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal[
        "good", "missing", "stuck", "out_of_range", "noisy", "rate_invalid", "driver_error"
    ]
    valid_samples: int = Field(ge=0)
    expected_samples: int = Field(ge=1)
    error_code: str | None = Field(default=None, max_length=48)


class SampleQuality(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temperature: SensorQuality
    vibration: SensorQuality
    current: SensorQuality


class Measurements(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temperature_c: float | None = Field(ge=-80, le=200)
    vibration_rms_mps2: float | None = Field(ge=0, le=2000)
    vibration_peak_mps2: float | None = Field(ge=0, le=4000)
    vibration_crest_factor: float | None = Field(ge=0, le=100)
    current_a: float | None = Field(ge=-0.1, le=10)


class TelemetryEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    message_id: UUID
    site_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,62}$")
    device_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,62}$")
    sequence: int = Field(ge=0)
    device_time: datetime | None
    clock_synchronized: bool
    uptime_ms: int = Field(ge=0)
    firmware_version: str = Field(max_length=48)
    quality: Literal["good", "degraded", "bad"]
    replayed: bool
    measurements: Measurements
    sample_quality: SampleQuality
    fault_flags: list[str] = Field(max_length=32)

    @model_validator(mode="after")
    def clock_state_is_consistent(self) -> TelemetryEnvelope:
        if not self.clock_synchronized and self.device_time is not None:
            raise ValueError("device_time must be null when clock is not synchronized")
        if self.clock_synchronized and self.device_time is None:
            raise ValueError("device_time is required when clock is synchronized")
        return self


class DeviceView(BaseModel):
    id: str
    site_id: str
    display_name: str
    asset_class: str
    simulated: bool
    firmware_version: str | None
    status: Literal["online", "degraded", "offline"]
    last_seen_at: datetime | None
    rssi_dbm: int | None
    reset_reason: str | None
    reset_count: int
    queue_depth: int
    queue_capacity: int
    dropped_message_count: int
    modbus_status: str
    active_faults: list[str]


class TelemetryView(BaseModel):
    message_id: str
    sequence: int
    device_time: datetime | None
    received_at: datetime
    quality: str
    replayed: bool
    temperature_c: float | None
    vibration_rms_mps2: float | None
    vibration_peak_mps2: float | None
    vibration_crest_factor: float | None
    current_a: float | None
    fault_flags: list[str]
    anomaly_score: float | None
    anomaly_percentile: float | None
    anomaly_reason: str | None


class TelemetryPage(BaseModel):
    items: list[TelemetryView]
    count: int
    limit: int


class AnomalyModelView(BaseModel):
    device_id: str
    status: Literal["model_not_ready", "ready", "stale", "error"]
    ready: bool
    diagnostic: str
    model_version: str | None = None
    feature_schema_version: int | None = None
    feature_names: list[str] = Field(default_factory=list)
    training_start: datetime | None = None
    training_end: datetime | None = None
    training_sample_count: int = 0
    validation_sample_count: int = 0
    contamination: float | None = None
    random_seed: int | None = None
    sklearn_version: str | None = None
    created_at: datetime | None = None
    last_scored_at: datetime | None = None
    score_interpretation: str = "higher is more anomalous; percentile is empirical, not probability"
    field_performance_claimed: Literal[False] = False


class IngestResult(BaseModel):
    status: Literal["inserted", "duplicate"]
    message_id: str


class HealthEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    message_id: UUID
    site_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,62}$")
    device_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,62}$")
    sequence: int = Field(ge=0)
    device_time: datetime | None
    uptime_ms: int = Field(ge=0)
    firmware_version: str = Field(max_length=48)
    status: Literal["online", "degraded", "offline"]
    rssi_dbm: int | None = Field(ge=-127, le=0)
    reset_reason: str = Field(max_length=48)
    reset_count: int = Field(ge=0)
    queue_depth: int = Field(ge=0)
    queue_capacity: int = Field(ge=1)
    dropped_message_count: int = Field(ge=0)
    modbus_status: Literal["ok", "timeout", "crc_error", "exception", "stale", "disabled"]
    active_faults: list[str] = Field(max_length=32)


class CommandAckEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    message_id: UUID
    command_id: UUID
    site_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,62}$")
    device_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,62}$")
    device_time: datetime | None
    status: Literal["accepted", "completed", "rejected", "expired", "failed"]
    result_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,47}$")
    detail: str | None = Field(default=None, max_length=240)
    relay_on: bool


class AlarmView(BaseModel):
    id: int
    device_id: str
    code: str
    severity: Literal["warning", "critical"]
    source: str
    state: Literal["active", "cleared"]
    summary: str
    opened_at: datetime
    cleared_at: datetime | None
    acknowledged_at: datetime | None
    acknowledged_by: str | None


class CalibrationCreate(BaseModel):
    sensor: Literal["temperature", "vibration", "current"]
    new_coefficients: dict[str, float] = Field(min_length=1, max_length=8)
    reason: str = Field(min_length=4, max_length=240)

    @model_validator(mode="after")
    def coefficients_are_bounded(self) -> CalibrationCreate:
        if not set(self.new_coefficients).issubset({"scale", "offset"}):
            raise ValueError("only scale and offset coefficients are supported")
        if "scale" in self.new_coefficients and not 0.1 <= self.new_coefficients["scale"] <= 10:
            raise ValueError("scale must be between 0.1 and 10")
        if "offset" in self.new_coefficients and not -100 <= self.new_coefficients["offset"] <= 100:
            raise ValueError("offset must be between -100 and 100")
        return self


class CalibrationView(BaseModel):
    id: int
    device_id: str
    sensor: str
    previous_coefficients: dict[str, float]
    new_coefficients: dict[str, float]
    reason: str
    operator: str
    performed_at: datetime


class MaintenanceCreate(BaseModel):
    status: Literal["scheduled", "completed", "deferred"]
    notes: str = Field(min_length=3, max_length=4000)
    performed_at: datetime
    next_due_at: datetime | None = None

    @model_validator(mode="after")
    def due_date_is_after_work(self) -> MaintenanceCreate:
        if self.next_due_at is not None and self.next_due_at <= self.performed_at:
            raise ValueError("next_due_at must be after performed_at")
        return self


class MaintenanceUpdate(BaseModel):
    status: Literal["scheduled", "completed", "deferred"] | None = None
    notes: str | None = Field(default=None, min_length=3, max_length=4000)
    next_due_at: datetime | None = None


class MaintenanceView(BaseModel):
    id: int
    device_id: str
    status: str
    notes: str
    performed_at: datetime
    next_due_at: datetime | None
    created_by: str
    updated_at: datetime


class RelayCommandCreate(BaseModel):
    relay_on: bool
    timeout_s: int = Field(default=10, ge=1, le=30)


class CommandView(BaseModel):
    command_id: str
    device_id: str
    kind: str
    parameters: dict[str, object]
    status: str
    result_code: str | None
    detail: str | None
    issued_by: str
    issued_at: datetime
    expires_at: datetime
    acknowledged_at: datetime | None


class ThresholdConfigUpdate(BaseModel):
    temperature_warning_c: float = Field(ge=0, le=150)
    temperature_critical_c: float = Field(ge=0, le=180)
    vibration_warning_mps2: float = Field(ge=0, le=200)
    vibration_critical_mps2: float = Field(ge=0, le=400)
    current_warning_a: float = Field(ge=0, le=8)
    current_critical_a: float = Field(ge=0, le=10)
    hysteresis_percent: float = Field(ge=1, le=25)

    @model_validator(mode="after")
    def warnings_are_below_critical(self) -> ThresholdConfigUpdate:
        pairs = (
            (self.temperature_warning_c, self.temperature_critical_c),
            (self.vibration_warning_mps2, self.vibration_critical_mps2),
            (self.current_warning_a, self.current_critical_a),
        )
        if any(warning >= critical for warning, critical in pairs):
            raise ValueError("each warning threshold must be below its critical threshold")
        return self


class ThresholdConfigView(ThresholdConfigUpdate):
    device_id: str
    updated_by: str
    updated_at: datetime


def normalized_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
