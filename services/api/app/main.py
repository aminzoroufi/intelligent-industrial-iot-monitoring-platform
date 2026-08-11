# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""FastAPI application for authenticated monitoring access."""

from __future__ import annotations

import asyncio
import csv
import io
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from services.api.app.command_service import issue_relay_command
from services.api.app.database import get_db
from services.api.app.events import notify_after_commit
from services.api.app.ingestion import SequenceCollisionError, persist_telemetry
from services.api.app.live import LiveConnectionManager, bearer_subprotocol_token, listen_for_events
from services.api.app.models import (
    Alarm,
    AuditEvent,
    Calibration,
    Device,
    DeviceCommand,
    MaintenanceRecord,
    Telemetry,
    ThresholdConfig,
    User,
    utc_now,
)
from services.api.app.schemas import (
    AlarmView,
    CalibrationCreate,
    CalibrationView,
    CommandView,
    DeviceView,
    IngestResult,
    MaintenanceCreate,
    MaintenanceUpdate,
    MaintenanceView,
    RelayCommandCreate,
    TelemetryEnvelope,
    TelemetryPage,
    TelemetryView,
    ThresholdConfigUpdate,
    ThresholdConfigView,
    TokenResponse,
    UserView,
)
from services.api.app.security import (
    CurrentUser,
    create_access_token,
    decode_access_token,
    verify_password,
)
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


def ensure_admin(user: User) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")


def to_alarm_view(alarm: Alarm) -> AlarmView:
    return AlarmView(
        id=alarm.id,
        device_id=alarm.device_id,
        code=alarm.code,
        severity=alarm.severity,  # type: ignore[arg-type]
        source=alarm.source,
        state=alarm.state,  # type: ignore[arg-type]
        summary=alarm.summary,
        opened_at=alarm.opened_at,
        cleared_at=alarm.cleared_at,
        acknowledged_at=alarm.acknowledged_at,
        acknowledged_by=alarm.acknowledged_by,
    )


def to_calibration_view(calibration: Calibration) -> CalibrationView:
    return CalibrationView(
        id=calibration.id,
        device_id=calibration.device_id,
        sensor=calibration.sensor,
        previous_coefficients=calibration.previous_coefficients,
        new_coefficients=calibration.new_coefficients,
        reason=calibration.reason,
        operator=calibration.operator,
        performed_at=calibration.performed_at,
    )


def to_maintenance_view(record: MaintenanceRecord) -> MaintenanceView:
    return MaintenanceView(
        id=record.id,
        device_id=record.device_id,
        status=record.status,
        notes=record.notes,
        performed_at=record.performed_at,
        next_due_at=record.next_due_at,
        created_by=record.created_by,
        updated_at=record.updated_at,
    )


def to_command_view(command: DeviceCommand) -> CommandView:
    return CommandView(
        command_id=command.command_id,
        device_id=command.device_id,
        kind=command.kind,
        parameters=command.parameters,
        status=command.status,
        result_code=command.result_code,
        detail=command.detail,
        issued_by=command.issued_by,
        issued_at=command.issued_at,
        expires_at=command.expires_at,
        acknowledged_at=command.acknowledged_at,
    )


def to_threshold_view(config: ThresholdConfig) -> ThresholdConfigView:
    return ThresholdConfigView(
        device_id=config.device_id,
        temperature_warning_c=config.temperature_warning_c,
        temperature_critical_c=config.temperature_critical_c,
        vibration_warning_mps2=config.vibration_warning_mps2,
        vibration_critical_mps2=config.vibration_critical_mps2,
        current_warning_a=config.current_warning_a,
        current_critical_a=config.current_critical_a,
        hysteresis_percent=config.hysteresis_percent,
        updated_by=config.updated_by,
        updated_at=config.updated_at,
    )


def safe_csv_text(value: str) -> str:
    if value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{value}"
    return value


def bounded_range(
    start: datetime | None,
    end: datetime | None,
    settings: Settings,
) -> tuple[datetime, datetime]:
    range_end = end or datetime.now(UTC)
    range_start = start or range_end - timedelta(hours=24)
    if range_end <= range_start:
        raise HTTPException(status_code=422, detail="end must be after start")
    if range_end - range_start > timedelta(days=settings.max_query_days):
        raise HTTPException(status_code=422, detail="requested time range is too large")
    return range_start, range_end


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    live_manager = LiveConnectionManager()
    stop_event = asyncio.Event()

    @asynccontextmanager
    async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
        listener = asyncio.create_task(listen_for_events(resolved, live_manager, stop_event))
        yield
        stop_event.set()
        listener.cancel()
        with suppress(asyncio.CancelledError):
            await listener

    application = FastAPI(
        title="Industrial IoT Monitoring API",
        version="0.1.0",
        description="Authenticated API for the low-voltage condition-monitoring demonstrator.",
        lifespan=lifespan,
    )
    application.state.settings = resolved
    application.dependency_overrides[get_settings] = lambda: resolved
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH"],
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
        range_start, range_end = bounded_range(start, end, resolved)
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

    @application.get("/api/v1/alarms", response_model=list[AlarmView], tags=["alarms"])
    def list_alarms(
        _user: CurrentUser,
        db: Annotated[Session, Depends(get_db)],
        device_id: str | None = None,
        alarm_state: Literal["active", "cleared"] | None = Query(default=None, alias="state"),
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> list[AlarmView]:
        query: Select[tuple[Alarm]] = select(Alarm).order_by(Alarm.opened_at.desc()).limit(limit)
        if device_id:
            query = query.where(Alarm.device_id == device_id)
        if alarm_state:
            query = query.where(Alarm.state == alarm_state)
        return [to_alarm_view(alarm) for alarm in db.scalars(query)]

    @application.post(
        "/api/v1/alarms/{alarm_id}/acknowledge",
        response_model=AlarmView,
        tags=["alarms"],
    )
    def acknowledge_alarm(
        alarm_id: int,
        user: CurrentUser,
        db: Annotated[Session, Depends(get_db)],
    ) -> AlarmView:
        alarm = db.get(Alarm, alarm_id)
        if alarm is None:
            raise HTTPException(status_code=404, detail="Alarm not found")
        if alarm.acknowledged_at is None:
            alarm.acknowledged_at = utc_now()
            alarm.acknowledged_by = user.username
            db.add(
                AuditEvent(
                    actor=user.username,
                    action="alarm_acknowledged",
                    target_type="alarm",
                    target_id=str(alarm.id),
                    details={"device_id": alarm.device_id, "code": alarm.code},
                )
            )
            notify_after_commit(
                db,
                {
                    "type": "alarm_acknowledged",
                    "device_id": alarm.device_id,
                    "alarm_id": alarm.id,
                    "acknowledged_by": user.username,
                },
            )
            db.commit()
        return to_alarm_view(alarm)

    @application.get(
        "/api/v1/devices/{device_id}/calibrations",
        response_model=list[CalibrationView],
        tags=["calibration"],
    )
    def list_calibrations(
        device_id: str,
        _user: CurrentUser,
        db: Annotated[Session, Depends(get_db)],
    ) -> list[CalibrationView]:
        rows = db.scalars(
            select(Calibration)
            .where(Calibration.device_id == device_id)
            .order_by(Calibration.performed_at.desc())
            .limit(200)
        )
        return [to_calibration_view(row) for row in rows]

    @application.post(
        "/api/v1/devices/{device_id}/calibrations",
        response_model=CalibrationView,
        status_code=201,
        tags=["calibration"],
    )
    def create_calibration(
        device_id: str,
        request: CalibrationCreate,
        user: CurrentUser,
        db: Annotated[Session, Depends(get_db)],
    ) -> CalibrationView:
        ensure_admin(user)
        if db.get(Device, device_id) is None:
            raise HTTPException(status_code=404, detail="Device not found")
        latest = db.scalar(
            select(Calibration)
            .where(Calibration.device_id == device_id, Calibration.sensor == request.sensor)
            .order_by(Calibration.performed_at.desc())
            .limit(1)
        )
        previous = latest.new_coefficients if latest else {"scale": 1.0, "offset": 0.0}
        row = Calibration(
            device_id=device_id,
            sensor=request.sensor,
            previous_coefficients=previous,
            new_coefficients=request.new_coefficients,
            reason=request.reason,
            operator=user.username,
        )
        db.add(row)
        db.flush()
        db.add(
            AuditEvent(
                actor=user.username,
                action="calibration_created",
                target_type="calibration",
                target_id=str(row.id),
                details={"device_id": device_id, "sensor": request.sensor},
            )
        )
        db.commit()
        return to_calibration_view(row)

    @application.get(
        "/api/v1/devices/{device_id}/maintenance",
        response_model=list[MaintenanceView],
        tags=["maintenance"],
    )
    def list_maintenance(
        device_id: str,
        _user: CurrentUser,
        db: Annotated[Session, Depends(get_db)],
    ) -> list[MaintenanceView]:
        rows = db.scalars(
            select(MaintenanceRecord)
            .where(MaintenanceRecord.device_id == device_id)
            .order_by(MaintenanceRecord.performed_at.desc())
            .limit(200)
        )
        return [to_maintenance_view(row) for row in rows]

    @application.post(
        "/api/v1/devices/{device_id}/maintenance",
        response_model=MaintenanceView,
        status_code=201,
        tags=["maintenance"],
    )
    def create_maintenance(
        device_id: str,
        request: MaintenanceCreate,
        user: CurrentUser,
        db: Annotated[Session, Depends(get_db)],
    ) -> MaintenanceView:
        if db.get(Device, device_id) is None:
            raise HTTPException(status_code=404, detail="Device not found")
        row = MaintenanceRecord(
            device_id=device_id,
            status=request.status,
            notes=request.notes,
            performed_at=request.performed_at,
            next_due_at=request.next_due_at,
            created_by=user.username,
        )
        db.add(row)
        db.flush()
        db.add(
            AuditEvent(
                actor=user.username,
                action="maintenance_created",
                target_type="maintenance",
                target_id=str(row.id),
                details={"device_id": device_id, "status": request.status},
            )
        )
        db.commit()
        return to_maintenance_view(row)

    @application.patch(
        "/api/v1/maintenance/{record_id}",
        response_model=MaintenanceView,
        tags=["maintenance"],
    )
    def update_maintenance(
        record_id: int,
        request: MaintenanceUpdate,
        user: CurrentUser,
        db: Annotated[Session, Depends(get_db)],
    ) -> MaintenanceView:
        row = db.get(MaintenanceRecord, record_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Maintenance record not found")
        if request.status is not None:
            row.status = request.status
        if request.notes is not None:
            row.notes = request.notes
        if "next_due_at" in request.model_fields_set:
            row.next_due_at = request.next_due_at
        if row.next_due_at is not None and row.next_due_at <= row.performed_at:
            raise HTTPException(status_code=422, detail="next_due_at must be after performed_at")
        row.updated_at = utc_now()
        db.add(
            AuditEvent(
                actor=user.username,
                action="maintenance_updated",
                target_type="maintenance",
                target_id=str(row.id),
                details={"device_id": row.device_id},
            )
        )
        db.commit()
        return to_maintenance_view(row)

    @application.get(
        "/api/v1/devices/{device_id}/thresholds",
        response_model=ThresholdConfigView,
        tags=["devices"],
    )
    def get_thresholds(
        device_id: str,
        _user: CurrentUser,
        db: Annotated[Session, Depends(get_db)],
    ) -> ThresholdConfigView:
        if db.get(Device, device_id) is None:
            raise HTTPException(status_code=404, detail="Device not found")
        config = db.get(ThresholdConfig, device_id)
        if config is None:
            config = ThresholdConfig(device_id=device_id)
            db.add(config)
            db.commit()
        return to_threshold_view(config)

    @application.put(
        "/api/v1/devices/{device_id}/thresholds",
        response_model=ThresholdConfigView,
        tags=["devices"],
    )
    def update_thresholds(
        device_id: str,
        request: ThresholdConfigUpdate,
        user: CurrentUser,
        db: Annotated[Session, Depends(get_db)],
    ) -> ThresholdConfigView:
        ensure_admin(user)
        if db.get(Device, device_id) is None:
            raise HTTPException(status_code=404, detail="Device not found")
        config = db.get(ThresholdConfig, device_id) or ThresholdConfig(device_id=device_id)
        for name, value in request.model_dump().items():
            setattr(config, name, value)
        config.updated_by = user.username
        config.updated_at = utc_now()
        db.add(config)
        db.add(
            AuditEvent(
                actor=user.username,
                action="thresholds_updated",
                target_type="device",
                target_id=device_id,
                details=request.model_dump(),
            )
        )
        db.commit()
        return to_threshold_view(config)

    @application.post(
        "/api/v1/devices/{device_id}/commands/relay",
        response_model=CommandView,
        status_code=202,
        tags=["commands"],
    )
    def create_relay_command(
        device_id: str,
        request: RelayCommandCreate,
        user: CurrentUser,
        db: Annotated[Session, Depends(get_db)],
    ) -> CommandView:
        ensure_admin(user)
        device = db.get(Device, device_id)
        if device is None:
            raise HTTPException(status_code=404, detail="Device not found")
        command = issue_relay_command(
            db,
            device=device,
            actor=user.username,
            request=request,
            settings=resolved,
        )
        return to_command_view(command)

    @application.get(
        "/api/v1/devices/{device_id}/commands",
        response_model=list[CommandView],
        tags=["commands"],
    )
    def list_commands(
        device_id: str,
        _user: CurrentUser,
        db: Annotated[Session, Depends(get_db)],
    ) -> list[CommandView]:
        rows = db.scalars(
            select(DeviceCommand)
            .where(DeviceCommand.device_id == device_id)
            .order_by(DeviceCommand.issued_at.desc())
            .limit(100)
        )
        return [to_command_view(row) for row in rows]

    @application.get(
        "/api/v1/devices/{device_id}/export.csv",
        response_class=StreamingResponse,
        tags=["telemetry"],
    )
    def export_telemetry(
        device_id: str,
        metric: Literal[
            "temperature_c",
            "vibration_rms_mps2",
            "vibration_peak_mps2",
            "current_a",
        ],
        _user: CurrentUser,
        db: Annotated[Session, Depends(get_db)],
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> StreamingResponse:
        range_start, range_end = bounded_range(start, end, resolved)
        rows = list(
            db.scalars(
                select(Telemetry)
                .where(
                    Telemetry.device_id == device_id,
                    Telemetry.received_at >= range_start,
                    Telemetry.received_at <= range_end,
                )
                .order_by(Telemetry.received_at)
                .limit(10_000)
            )
        )

        def csv_stream() -> Iterator[str]:
            buffer = io.StringIO()
            writer = csv.writer(buffer, lineterminator="\n")
            writer.writerow(
                ["device_id", "received_at_utc", "metric", "value", "quality", "fault_flags"]
            )
            yield buffer.getvalue()
            for row in rows:
                buffer.seek(0)
                buffer.truncate(0)
                writer.writerow(
                    [
                        safe_csv_text(row.device_id),
                        row.received_at.isoformat(),
                        metric,
                        getattr(row, metric),
                        safe_csv_text(row.quality),
                        safe_csv_text("|".join(row.fault_flags)),
                    ]
                )
                yield buffer.getvalue()

        filename = f"{device_id}-{metric}.csv"
        return StreamingResponse(
            csv_stream(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @application.websocket("/api/v1/ws")
    async def live_events(websocket: WebSocket) -> None:
        token = bearer_subprotocol_token(websocket.headers.get("sec-websocket-protocol"))
        if token is None:
            await websocket.close(code=4401, reason="Missing bearer subprotocol")
            return
        try:
            username = decode_access_token(token, resolved)
        except HTTPException:
            await websocket.close(code=4401, reason="Invalid access token")
            return

        from services.api.app.database import SessionLocal

        with SessionLocal() as session:
            user = session.scalar(
                select(User).where(User.username == username, User.active.is_(True))
            )
        if user is None:
            await websocket.close(code=4403, reason="Inactive user")
            return

        await live_manager.connect(websocket, subprotocol="bearer")
        await websocket.send_json({"type": "connected", "username": username})
        try:
            while True:
                message = await websocket.receive_text()
                if message == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            live_manager.disconnect(websocket)

    return application


app = create_app()
