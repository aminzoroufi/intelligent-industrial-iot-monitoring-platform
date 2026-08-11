# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""Canonical MQTT topic construction and validation."""

from __future__ import annotations

import re
from enum import StrEnum

TOPIC_VERSION = "v1"
TOPIC_ROOT = "iiot"
MAX_PAYLOAD_BYTES = 16 * 1024
IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


class TopicKind(StrEnum):
    TELEMETRY = "telemetry"
    HEALTH = "health"
    EVENTS = "events"
    COMMANDS = "commands"
    COMMAND_ACKS = "command-acks"
    AVAILABILITY = "availability"


def topic(site_id: str, device_id: str, kind: TopicKind) -> str:
    """Build a validated version-1 topic."""
    for name, value in (("site_id", site_id), ("device_id", device_id)):
        if not IDENTIFIER_PATTERN.fullmatch(value):
            raise ValueError(f"invalid {name}")
    return f"{TOPIC_ROOT}/{TOPIC_VERSION}/{site_id}/{device_id}/{kind.value}"


def telemetry_subscription() -> str:
    """Return the broker subscription for every version-1 telemetry stream."""
    return f"{TOPIC_ROOT}/{TOPIC_VERSION}/+/+/{TopicKind.TELEMETRY.value}"
