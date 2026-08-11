# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""Deterministic, clearly synthetic MQTT telemetry scenario publisher."""

from __future__ import annotations

import argparse
import json
import math
import random
import time
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from contracts.mqtt_topics import TopicKind, topic

SCENARIOS = (
    "normal",
    "rising-temperature",
    "vibration-imbalance",
    "current-overload",
    "sensor-stuck",
)


def scenario_values(name: str, count: int, seed: int = 20260811) -> Iterator[dict[str, Any]]:
    rng = random.Random(seed)  # noqa: S311 - deterministic synthetic fixture, not security
    stuck_temperature = 41.75
    for index in range(count):
        phase = index / max(count - 1, 1)
        temperature_c = 41.5 + 0.5 * math.sin(index / 8) + rng.uniform(-0.12, 0.12)
        vibration_rms_mps2 = 1.15 + rng.uniform(-0.08, 0.08)
        vibration_peak_mps2 = vibration_rms_mps2 * (2.2 + rng.uniform(-0.12, 0.12))
        current_a = 0.63 + rng.uniform(-0.025, 0.025)
        quality = "good"
        fault_flags: list[str] = []
        temperature_status = "good"

        if name == "rising-temperature":
            temperature_c += 32 * phase
            if temperature_c >= 65:
                quality = "degraded"
                fault_flags.append("TEMPERATURE_WARNING")
        elif name == "vibration-imbalance":
            vibration_rms_mps2 += 5.2 * phase
            vibration_peak_mps2 = vibration_rms_mps2 * (2.7 + 0.8 * phase)
            if vibration_rms_mps2 >= 4.5:
                quality = "degraded"
                fault_flags.append("VIBRATION_WARNING")
        elif name == "current-overload":
            current_a += 1.25 * phase
            if current_a >= 1.4:
                quality = "degraded"
                fault_flags.append("CURRENT_OVERLOAD_WARNING")
        elif name == "sensor-stuck":
            temperature_c = stuck_temperature
            if index >= 8:
                quality = "bad"
                temperature_status = "stuck"
                fault_flags.append("TEMPERATURE_SENSOR_STUCK")
        elif name != "normal":
            raise ValueError(f"unsupported scenario: {name}")

        yield {
            "temperature_c": round(temperature_c, 3),
            "vibration_rms_mps2": round(vibration_rms_mps2, 4),
            "vibration_peak_mps2": round(vibration_peak_mps2, 4),
            "vibration_crest_factor": round(
                vibration_peak_mps2 / max(vibration_rms_mps2, 0.0001), 3
            ),
            "current_a": round(current_a, 4),
            "quality": quality,
            "fault_flags": fault_flags,
            "temperature_status": temperature_status,
        }


def build_envelope(
    values: dict[str, Any],
    sequence: int,
    device_time: datetime,
    session_id: str,
) -> dict[str, Any]:
    device_id = "motor-01"
    message_id = uuid.uuid5(uuid.NAMESPACE_URL, f"iiot:{session_id}:{device_id}:{sequence}")
    return {
        "schema_version": 1,
        "message_id": str(message_id),
        "site_id": "workshop-demo",
        "device_id": device_id,
        "sequence": sequence,
        "device_time": device_time.isoformat().replace("+00:00", "Z"),
        "clock_synchronized": True,
        "uptime_ms": (sequence + 1) * 10_000,
        "firmware_version": "0.1.0-sim",
        "quality": values["quality"],
        "replayed": False,
        "measurements": {
            "temperature_c": values["temperature_c"],
            "vibration_rms_mps2": values["vibration_rms_mps2"],
            "vibration_peak_mps2": values["vibration_peak_mps2"],
            "vibration_crest_factor": values["vibration_crest_factor"],
            "current_a": values["current_a"],
        },
        "sample_quality": {
            "temperature": {
                "status": values["temperature_status"],
                "valid_samples": 10,
                "expected_samples": 10,
                "error_code": None,
            },
            "vibration": {
                "status": "good",
                "valid_samples": 256,
                "expected_samples": 256,
                "error_code": None,
            },
            "current": {
                "status": "good",
                "valid_samples": 50,
                "expected_samples": 50,
                "error_code": None,
            },
        },
        "fault_flags": values["fault_flags"],
    }


def publish(args: argparse.Namespace) -> None:
    client = mqtt.Client(CallbackAPIVersion.VERSION2, client_id=f"sim-{args.session_id}")
    client.connect(args.host, args.port, keepalive=30)
    client.loop_start()
    start = datetime.fromisoformat(args.start_time.replace("Z", "+00:00")).astimezone(UTC)
    telemetry_topic = topic("workshop-demo", "motor-01", TopicKind.TELEMETRY)
    try:
        for offset, values in enumerate(scenario_values(args.scenario, args.count, args.seed)):
            sequence = args.sequence_start + offset
            envelope = build_envelope(
                values,
                sequence,
                start + timedelta(seconds=10 * offset),
                args.session_id,
            )
            info = client.publish(telemetry_topic, json.dumps(envelope), qos=1, retain=False)
            info.wait_for_publish(timeout=10)
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                raise RuntimeError(f"publish failed with MQTT code {info.rc}")
            print(
                json.dumps(
                    {
                        "synthetic": True,
                        "scenario": args.scenario,
                        "sequence": sequence,
                        "message_id": envelope["message_id"],
                    }
                )
            )
            if args.interval_s > 0:
                time.sleep(args.interval_s)
    finally:
        client.disconnect()
        client.loop_stop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=SCENARIOS)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--count", type=int, default=30)
    parser.add_argument("--interval-s", type=float, default=0.2)
    parser.add_argument("--sequence-start", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260811)
    parser.add_argument("--session-id", default="local-demo")
    parser.add_argument("--start-time", default="2026-08-11T08:00:00Z")
    return parser.parse_args()


if __name__ == "__main__":
    publish(parse_args())
