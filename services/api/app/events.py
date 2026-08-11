# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""Compact PostgreSQL notifications for cross-process live updates."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

EVENT_CHANNEL = "iiot_events"


def notify_after_commit(session: Session, event: dict[str, Any]) -> None:
    """Queue a transaction-bound PostgreSQL NOTIFY; SQLite tests safely skip it."""
    if session.bind is None or session.bind.dialect.name != "postgresql":
        return
    payload = json.dumps(event, separators=(",", ":"), default=str)
    if len(payload.encode()) > 7000:
        raise ValueError("live event exceeds bounded PostgreSQL notification size")
    session.execute(
        text("SELECT pg_notify(:channel, :payload)"), {"channel": EVENT_CHANNEL, "payload": payload}
    )
