# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""FastAPI application for authenticated monitoring access."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from services.api.app.database import get_db
from services.api.app.ingestion import SequenceCollisionError, persist_telemetry
from services.api.app.models import Device, Telemetry, User
from services.api.app.schemas import (
    DeviceView,
    IngestResult,
    TelemetryEnvelope,
    TelemetryPage,
    TelemetryView,
    TokenResponse,
    UserView,
)
from services.api.app.security import CurrentUser, create_access_token, verify_password
from services.api.app.settings import Settings, get_settings


def device_status(
    device: Device, settings: Settings, now: datetime | None = None
) -> Literal["online", "degraded", "offline"]:
    reference = now or datetime.now(UTC)
    if device.last_seen_at is None:
        return "offline"
    last_seen = device.last_seen_at
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=UTC)
    if reference - last_seen > timedelta(seconds=settings.offline_after_s):
        return "offline"
    if device.reported_status != "online" or device.active_faults:
        return "degraded"
    return "online"


def to_device_view(device: Device, settings: Settings) -> DeviceView:
    return DeviceView(
        id=device.id,
        site_id=device.site_id,
        display_name=device.display_name,
        asset_class=device.asset_class,
        simulated=device.simulated,
        firmware_version=device.firmware_version,
        status=device_status(device, settings),
        last_seen_at=device.last_seen_at,
        rssi_dbm=device.rssi_dbm,
        reset_reason=device.reset_reason,
        reset_count=device.reset_count,
        queue_depth=device.queue_depth,
        queue_capacity=device.queue_capacity,
        dropped_message_count=device.dropped_message_count,
        modbus_status=device.modbus_status,
        active_faults=device.active_faults,
    )


def to_telemetry_view(row: Telemetry) -> TelemetryView:
    return TelemetryView(
        message_id=row.message_id,
        sequence=row.sequence,
        device_time=row.device_time,
        received_at=row.received_at,
        quality=row.quality,
        replayed=row.replayed,
        temperature_c=row.temperature_c,
        vibration_rms_mps2=row.vibration_rms_mps2,
        vibration_peak_mps2=row.vibration_peak_mps2,
        vibration_crest_factor=row.vibration_crest_factor,
        current_a=row.current_a,
        fault_flags=row.fault_flags,
        anomaly_score=row.anomaly_score,
        anomaly_percentile=row.anomaly_percentile,
        anomaly_reason=row.anomaly_reason,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    application = FastAPI(
        title="Industrial IoT Monitoring API",
        version="0.1.0",
        description="Authenticated API for the low-voltage condition-monitoring demonstrator.",
    )
    application.state.settings = resolved
    application.dependency_overrides[get_settings] = lambda: resolved
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @application.get("/healthz", tags=["system"])
    def healthz() -> dict[str, str]:
        return {"status": "ok", "service": "api"}

    @application.post("/api/v1/auth/token", response_model=TokenResponse, tags=["auth"])
    def login(
        form: Annotated[OAuth2PasswordRequestForm, Depends()],
        db: Annotated[Session, Depends(get_db)],
    ) -> TokenResponse:
        user = db.scalar(select(User).where(User.username == form.username, User.active.is_(True)))
        if user is None or not verify_password(form.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        token, expires_in_s = create_access_token(user.username, resolved)
        return TokenResponse(access_token=token, expires_in_s=expires_in_s)

    @application.get("/api/v1/auth/me", response_model=UserView, tags=["auth"])
    def me(user: CurrentUser) -> UserView:
        return UserView(username=user.username, role=user.role)

    @application.get("/api/v1/devices", response_model=list[DeviceView], tags=["devices"])
    def list_devices(
        _user: CurrentUser,
        db: Annotated[Session, Depends(get_db)],
        site_id: str | None = None,
    ) -> list[DeviceView]:
        query: Select[tuple[Device]] = select(Device).order_by(Device.id)
        if site_id:
            query = query.where(Device.site_id == site_id)
        return [to_device_view(device, resolved) for device in db.scalars(query)]

    @application.get("/api/v1/devices/{device_id}", response_model=DeviceView, tags=["devices"])
    def get_device(
        device_id: str,
        _user: CurrentUser,
        db: Annotated[Session, Depends(get_db)],
    ) -> DeviceView:
        device = db.get(Device, device_id)
        if device is None:
            raise HTTPException(status_code=404, detail="Device not found")
        return to_device_view(device, resolved)

    @application.get(
        "/api/v1/devices/{device_id}/telemetry",
        response_model=TelemetryPage,
        tags=["telemetry"],
    )
    def list_telemetry(
        device_id: str,
        _user: CurrentUser,
        db: Annotated[Session, Depends(get_db)],
        start: datetime | None = None,
        end: datetime | None = None,
        limit: Annotated[int, Query(ge=1, le=2000)] = 500,
    ) -> TelemetryPage:
        range_end = end or datetime.now(UTC)
        range_start = start or range_end - timedelta(hours=24)
        if range_end <= range_start:
            raise HTTPException(status_code=422, detail="end must be after start")
        if range_end - range_start > timedelta(days=resolved.max_query_days):
            raise HTTPException(status_code=422, detail="requested time range is too large")
        query = (
            select(Telemetry)
            .where(
                Telemetry.device_id == device_id,
                Telemetry.received_at >= range_start,
                Telemetry.received_at <= range_end,
            )
            .order_by(Telemetry.received_at.desc())
            .limit(limit)
        )
        items = [to_telemetry_view(row) for row in db.scalars(query)]
        return TelemetryPage(items=items, count=len(items), limit=limit)

    @application.post("/internal/v1/telemetry", response_model=IngestResult, tags=["internal"])
    def ingest_telemetry(
        envelope: TelemetryEnvelope,
        db: Annotated[Session, Depends(get_db)],
        x_ingest_token: Annotated[str, Header()],
    ) -> IngestResult:
        if x_ingest_token != resolved.ingest_token.get_secret_value():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid ingest token"
            )
        try:
            result = persist_telemetry(db, envelope)
        except SequenceCollisionError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        return IngestResult(status=result.status, message_id=result.message_id)  # type: ignore[arg-type]

    return application


app = create_app()
