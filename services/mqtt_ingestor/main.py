# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""Independent MQTT consumer with contract validation and idempotent persistence."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from paho.mqtt.properties import Properties
from paho.mqtt.reasoncodes import ReasonCode
from pydantic import ValidationError

from contracts.mqtt_topics import MAX_PAYLOAD_BYTES, telemetry_subscription
from services.api.app.database import SessionLocal
from services.api.app.ingestion import SequenceCollisionError, persist_telemetry
from services.api.app.models import ErrorLog
from services.api.app.schemas import TelemetryEnvelope
from services.api.app.settings import Settings, get_settings

logging.basicConfig(level=logging.INFO, format="%(message)s")
LOGGER = logging.getLogger("mqtt-ingestor")
READY_PATH = Path("run/ingestor-ready")


@dataclass(frozen=True)
class ParsedTopic:
    site_id: str
    device_id: str


def parse_telemetry_topic(value: str) -> ParsedTopic:
    parts = value.split("/")
    if len(parts) != 5 or parts[0:2] != ["iiot", "v1"] or parts[4] != "telemetry":
        raise ValueError("topic is not a version-1 telemetry topic")
    return ParsedTopic(site_id=parts[2], device_id=parts[3])


def decode_payload(topic: str, payload: bytes) -> TelemetryEnvelope:
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise ValueError("payload exceeds 16 KiB contract limit")
    parsed_topic = parse_telemetry_topic(topic)
    try:
        raw: Any = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("payload is not valid UTF-8 JSON") from exc
    envelope = TelemetryEnvelope.model_validate(raw)
    if envelope.site_id != parsed_topic.site_id or envelope.device_id != parsed_topic.device_id:
        raise ValueError("topic and payload identities do not match")
    return envelope


def record_error(code: str, detail: str, device_id: str | None = None) -> None:
    with SessionLocal() as session:
        session.add(
            ErrorLog(
                component="mqtt-ingestor",
                error_code=code,
                severity="warning",
                device_id=device_id,
                detail=detail[:300],
            )
        )
        session.commit()


def handle_message(topic: str, payload: bytes) -> str:
    try:
        envelope = decode_payload(topic, payload)
        with SessionLocal() as session:
            result = persist_telemetry(session, envelope)
        LOGGER.info(
            json.dumps(
                {
                    "severity": "info",
                    "component": "mqtt-ingestor",
                    "event": "telemetry_persisted",
                    "device_id": envelope.device_id,
                    "message_id": result.message_id,
                    "status": result.status,
                }
            )
        )
        return result.status
    except ValidationError as exc:
        record_error("CONTRACT_VALIDATION", f"validation failed with {exc.error_count()} errors")
        return "rejected"
    except SequenceCollisionError as exc:
        record_error("SEQUENCE_COLLISION", str(exc))
        return "rejected"
    except ValueError as exc:
        record_error("INVALID_MESSAGE", str(exc))
        return "rejected"


def build_client(settings: Settings) -> mqtt.Client:
    client = mqtt.Client(CallbackAPIVersion.VERSION2, client_id="iiot-mqtt-ingestor")
    if settings.mqtt_username and settings.mqtt_password:
        client.username_pw_set(
            settings.mqtt_username,
            settings.mqtt_password.get_secret_value(),
        )

    def on_connect(
        connected_client: mqtt.Client,
        _userdata: object,
        _flags: mqtt.ConnectFlags,
        reason_code: ReasonCode,
        _properties: Properties | None,
    ) -> None:
        if reason_code.is_failure:
            LOGGER.error(
                json.dumps(
                    {
                        "severity": "error",
                        "component": "mqtt-ingestor",
                        "event": "broker_connection_rejected",
                        "reason": str(reason_code),
                    }
                )
            )
            return
        connected_client.subscribe(telemetry_subscription(), qos=1)
        READY_PATH.parent.mkdir(exist_ok=True)
        READY_PATH.touch()

    def on_disconnect(
        _connected_client: mqtt.Client,
        _userdata: object,
        _disconnect_flags: mqtt.DisconnectFlags,
        _reason_code: ReasonCode,
        _properties: Properties | None,
    ) -> None:
        READY_PATH.unlink(missing_ok=True)

    def on_message(
        _connected_client: mqtt.Client, _userdata: object, message: mqtt.MQTTMessage
    ) -> None:
        handle_message(message.topic, message.payload)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=60)
    return client


def main() -> None:
    settings = get_settings()
    client = build_client(settings)
    client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=30)
    client.loop_forever(retry_first_connection=True)


if __name__ == "__main__":
    main()
