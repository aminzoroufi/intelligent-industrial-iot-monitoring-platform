# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""Conservative MQTT command publication with durable audit state."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import NotRequired, TypedDict
from uuid import uuid4

import paho.mqtt.publish as mqtt_publish
from sqlalchemy.orm import Session

from contracts.mqtt_topics import TopicKind, topic
from services.api.app.models import AuditEvent, Device, DeviceCommand
from services.api.app.schemas import RelayCommandCreate
from services.api.app.settings import Settings


class MqttAuth(TypedDict):
    username: str
    password: NotRequired[str]


def issue_relay_command(
    session: Session,
    *,
    device: Device,
    actor: str,
    request: RelayCommandCreate,
    settings: Settings,
) -> DeviceCommand:
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=min(request.timeout_s, 10))
    command_id = str(uuid4())
    parameters: dict[str, object] = {
        "relay_on": request.relay_on,
        "timeout_s": request.timeout_s,
    }
    command = DeviceCommand(
        command_id=command_id,
        device_id=device.id,
        kind="set_demo_relay",
        parameters=parameters,
        status="queued",
        issued_by=actor,
        issued_at=now,
        expires_at=expires_at,
    )
    session.add(command)
    session.add(
        AuditEvent(
            actor=actor,
            action="relay_command_issued",
            target_type="device_command",
            target_id=command_id,
            details={"device_id": device.id, **parameters},
        )
    )
    session.commit()

    payload = {
        "schema_version": 1,
        "command_id": command_id,
        "site_id": device.site_id,
        "device_id": device.id,
        "issued_at": now.isoformat().replace("+00:00", "Z"),
        "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
        "issued_by": actor,
        "kind": "set_demo_relay",
        "parameters": parameters,
    }
    auth: MqttAuth | None = None
    if settings.mqtt_username and settings.mqtt_password:
        auth = {
            "username": settings.mqtt_username,
            "password": settings.mqtt_password.get_secret_value(),
        }
    try:
        mqtt_publish.single(
            topic(device.site_id, device.id, TopicKind.COMMANDS),
            payload=json.dumps(payload, separators=(",", ":")),
            qos=1,
            retain=False,
            hostname=settings.mqtt_host,
            port=settings.mqtt_port,
            auth=auth,
        )
        command.status = "published"
    except Exception as exc:
        command.status = "failed"
        command.result_code = "BROKER_PUBLISH_FAILED"
        command.detail = type(exc).__name__
    session.commit()
    return command
