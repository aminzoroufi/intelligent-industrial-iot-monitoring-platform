# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.mqtt_ingestor.main import (
    decode_command_ack,
    decode_health,
    decode_payload,
    parse_telemetry_topic,
)

ROOT = Path(__file__).parents[2]


def test_topic_and_payload_identity_match() -> None:
    payload = (ROOT / "contracts/examples/telemetry.normal.v1.json").read_bytes()
    envelope = decode_payload("iiot/v1/workshop-demo/motor-01/telemetry", payload)
    assert envelope.device_id == "motor-01"


def test_topic_payload_identity_mismatch_is_rejected() -> None:
    data = json.loads((ROOT / "contracts/examples/telemetry.normal.v1.json").read_text())
    data["device_id"] = "motor-02"
    with pytest.raises(ValueError, match="identities"):
        decode_payload(
            "iiot/v1/workshop-demo/motor-01/telemetry",
            json.dumps(data).encode(),
        )


def test_invalid_topic_is_rejected() -> None:
    with pytest.raises(ValueError, match="application topic"):
        parse_telemetry_topic("iiot/v2/workshop-demo/motor-01/telemetry")


def test_health_and_command_ack_contracts_decode() -> None:
    health = decode_health(
        "iiot/v1/workshop-demo/motor-01/health",
        (ROOT / "contracts/examples/health.v1.json").read_bytes(),
    )
    ack = decode_command_ack(
        "iiot/v1/workshop-demo/motor-01/command-acks",
        (ROOT / "contracts/examples/command-ack.v1.json").read_bytes(),
    )
    assert health.queue_capacity == 512
    assert ack.result_code == "RELAY_OFF"
