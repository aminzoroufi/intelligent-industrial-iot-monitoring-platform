# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""Regression tests for the safe-state simulated gateway."""

from __future__ import annotations

from typing import cast

import paho.mqtt.client as mqtt

from contracts.mqtt_topics import TopicKind, topic
from services.api.app.schemas import TelemetryEnvelope
from simulator.gateway_agent import DEVICE_ID, SITE_ID, GatewayAgent


class CapturingClient:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str, int, bool]] = []

    def publish(
        self,
        destination: str,
        payload: str,
        qos: int = 0,
        retain: bool = False,
    ) -> None:
        self.messages.append((destination, payload, qos, retain))


def test_gateway_publishes_contract_valid_normal_telemetry() -> None:
    agent = GatewayAgent("localhost", 1883)
    client = CapturingClient()
    agent.client = cast(mqtt.Client, client)
    sequence = agent.telemetry_sequence

    agent.publish_telemetry()

    assert len(client.messages) == 1
    destination, payload, qos, retain = client.messages[0]
    envelope = TelemetryEnvelope.model_validate_json(payload)
    assert destination == topic(SITE_ID, DEVICE_ID, TopicKind.TELEMETRY)
    assert qos == 1
    assert retain is False
    assert envelope.sequence == sequence
    assert envelope.quality == "good"
    assert envelope.device_id == DEVICE_ID
    assert envelope.measurements.temperature_c is not None
    assert agent.telemetry_sequence == sequence + 1
