# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""Validated API and device-contract models."""

from __future__ import annotations

from datetime import datetime
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


class IngestResult(BaseModel):
    status: Literal["inserted", "duplicate"]
    message_id: str
