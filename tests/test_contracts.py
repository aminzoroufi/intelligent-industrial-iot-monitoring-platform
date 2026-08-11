# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).parents[1]
SCHEMAS = ROOT / "contracts" / "schemas"
EXAMPLES = ROOT / "contracts" / "examples"

EXAMPLE_TO_SCHEMA = {
    "telemetry.normal.v1.json": "telemetry.v1.schema.json",
    "telemetry.sensor-fault.v1.json": "telemetry.v1.schema.json",
    "health.v1.json": "health.v1.schema.json",
    "event.warning.v1.json": "event.v1.schema.json",
    "command.relay-off.v1.json": "command.v1.schema.json",
    "command-ack.v1.json": "command-ack.v1.schema.json",
    "availability.online.v1.json": "availability.v1.schema.json",
}


@pytest.mark.parametrize(("example_name", "schema_name"), EXAMPLE_TO_SCHEMA.items())
def test_contract_example_matches_schema(example_name: str, schema_name: str) -> None:
    schema = json.loads((SCHEMAS / schema_name).read_text())
    example = json.loads((EXAMPLES / example_name).read_text())

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(example)


def test_unsynchronized_clock_requires_null_device_time() -> None:
    schema = json.loads((SCHEMAS / "telemetry.v1.schema.json").read_text())
    example = json.loads((EXAMPLES / "telemetry.normal.v1.json").read_text())
    example["clock_synchronized"] = False

    errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(example))

    assert errors
