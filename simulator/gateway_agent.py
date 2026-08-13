# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""Safe-state simulated gateway for health, availability, and command acknowledgements."""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from paho.mqtt.properties import Properties
from paho.mqtt.reasoncodes import ReasonCode
from pydantic import ValidationError

from contracts.mqtt_topics import TopicKind, topic
from services.api.app.schemas import RelayCommandCreate
from simulator.telemetry_generator.main import build_envelope, scenario_values

SITE_ID = "workshop-demo"
DEVICE_ID = "motor-01"
LOGGER = logging.getLogger("simulated-gateway")
logging.basicConfig(level=logging.INFO, format="%(message)s")


class GatewayAgent:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.started_monotonic = time.monotonic()
        self.sequence = 0
        self.telemetry_sequence = int(time.time())
        self.telemetry_values = scenario_values("normal", count=1_000_000)
        self.reset_count = 1
        self.relay_on = False
        self.relay_off_deadline: float | None = None
        self.ready_path = Path("run/simulated-gateway-ready")
        self.client = mqtt.Client(
            CallbackAPIVersion.VERSION2,
            client_id=f"simulated-gateway-{DEVICE_ID}",
        )
        offline = {
            "schema_version": 1,
            "site_id": SITE_ID,
            "device_id": DEVICE_ID,
            "status": "offline",
            "reason": "broker_lwt",
        }
        self.client.will_set(
            topic(SITE_ID, DEVICE_ID, TopicKind.AVAILABILITY),
            json.dumps(offline),
            qos=1,
            retain=True,
        )
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)

    def on_connect(
        self,
        client: mqtt.Client,
        _userdata: object,
        _flags: mqtt.ConnectFlags,
        reason_code: ReasonCode,
        _properties: Properties | None,
    ) -> None:
        if reason_code.is_failure:
            return
        client.subscribe(topic(SITE_ID, DEVICE_ID, TopicKind.COMMANDS), qos=1)
        online = {
            "schema_version": 1,
            "site_id": SITE_ID,
            "device_id": DEVICE_ID,
            "status": "online",
            "reason": "boot",
        }
        client.publish(
            topic(SITE_ID, DEVICE_ID, TopicKind.AVAILABILITY),
            json.dumps(online),
            qos=1,
            retain=True,
        )
        self.ready_path.parent.mkdir(exist_ok=True)
        self.ready_path.touch()

    def on_disconnect(
        self,
        _client: mqtt.Client,
        _userdata: object,
        _flags: mqtt.DisconnectFlags,
        _reason_code: ReasonCode,
        _properties: Properties | None,
    ) -> None:
        self.ready_path.unlink(missing_ok=True)
        self.relay_on = False
        self.relay_off_deadline = None

    def publish_ack(
        self,
        command_id: str,
        status: str,
        result_code: str,
        detail: str | None = None,
    ) -> None:
        payload = {
            "schema_version": 1,
            "message_id": str(uuid4()),
            "command_id": command_id,
            "site_id": SITE_ID,
            "device_id": DEVICE_ID,
            "device_time": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "status": status,
            "result_code": result_code,
            "detail": detail,
            "relay_on": self.relay_on,
        }
        self.client.publish(
            topic(SITE_ID, DEVICE_ID, TopicKind.COMMAND_ACKS),
            json.dumps(payload),
            qos=1,
        )

    def on_message(
        self, _client: mqtt.Client, _userdata: object, message: mqtt.MQTTMessage
    ) -> None:
        try:
            payload = json.loads(message.payload)
            command_id = str(payload["command_id"])
            if payload.get("device_id") != DEVICE_ID or payload.get("site_id") != SITE_ID:
                self.publish_ack(command_id, "rejected", "IDENTITY_MISMATCH")
                return
            expires_at = datetime.fromisoformat(str(payload["expires_at"]).replace("Z", "+00:00"))
            if datetime.now(UTC) >= expires_at:
                self.publish_ack(command_id, "expired", "COMMAND_EXPIRED")
                return
            if payload.get("kind") != "set_demo_relay":
                self.publish_ack(command_id, "rejected", "UNSUPPORTED_COMMAND")
                return
            request = RelayCommandCreate.model_validate(payload["parameters"])
            self.relay_on = request.relay_on
            self.relay_off_deadline = (
                time.monotonic() + request.timeout_s if request.relay_on else None
            )
            self.publish_ack(
                command_id,
                "completed",
                "RELAY_ON" if self.relay_on else "RELAY_OFF",
            )
        except (KeyError, TypeError, ValueError, ValidationError, json.JSONDecodeError) as exc:
            LOGGER.warning(
                json.dumps(
                    {
                        "severity": "warning",
                        "component": "simulated-gateway",
                        "event": "command_rejected",
                        "reason": type(exc).__name__,
                    }
                )
            )

    def publish_health(self) -> None:
        self.sequence += 1
        payload = {
            "schema_version": 1,
            "message_id": str(uuid4()),
            "site_id": SITE_ID,
            "device_id": DEVICE_ID,
            "sequence": self.sequence,
            "device_time": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "uptime_ms": int((time.monotonic() - self.started_monotonic) * 1000),
            "firmware_version": "0.1.0-sim",
            "status": "online",
            "rssi_dbm": -48,
            "reset_reason": "software_simulation_start",
            "reset_count": self.reset_count,
            "queue_depth": 0,
            "queue_capacity": 512,
            "dropped_message_count": 0,
            "modbus_status": "ok",
            "active_faults": [],
        }
        self.client.publish(
            topic(SITE_ID, DEVICE_ID, TopicKind.HEALTH),
            json.dumps(payload),
            qos=1,
            retain=True,
        )

    def publish_telemetry(self) -> None:
        payload = build_envelope(
            next(self.telemetry_values),
            self.telemetry_sequence,
            datetime.now(UTC),
            "simulated-gateway",
        )
        payload["message_id"] = str(uuid4())
        payload["uptime_ms"] = int((time.monotonic() - self.started_monotonic) * 1000)
        self.client.publish(
            topic(SITE_ID, DEVICE_ID, TopicKind.TELEMETRY),
            json.dumps(payload),
            qos=1,
            retain=False,
        )
        self.telemetry_sequence += 1

    def run(self) -> None:
        self.client.connect(self.host, self.port, keepalive=30)
        self.client.loop_start()
        next_health = 0.0
        next_telemetry = 0.0
        try:
            while True:
                now = time.monotonic()
                if now >= next_health:
                    self.publish_health()
                    next_health = now + 10
                if now >= next_telemetry:
                    self.publish_telemetry()
                    next_telemetry = now + 2
                if self.relay_off_deadline is not None and now >= self.relay_off_deadline:
                    self.relay_on = False
                    self.relay_off_deadline = None
                time.sleep(0.1)
        finally:
            self.relay_on = False
            self.client.disconnect()
            self.client.loop_stop()


def main() -> None:
    agent = GatewayAgent(
        host=os.getenv("IIOT_MQTT_HOST", "localhost"),
        port=int(os.getenv("IIOT_MQTT_PORT", "1883")),
    )
    agent.run()


if __name__ == "__main__":
    main()
