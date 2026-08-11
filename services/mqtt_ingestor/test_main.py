# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.mqtt_ingestor.main import decode_payload, parse_telemetry_topic

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
    with pytest.raises(ValueError, match="telemetry topic"):
        parse_telemetry_topic("iiot/v2/workshop-demo/motor-01/telemetry")
