# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from services.api.app.ingestion import SequenceCollisionError, persist_telemetry
from services.api.app.models import Telemetry
from services.api.app.schemas import TelemetryEnvelope

ROOT = Path(__file__).parents[3]


def load_envelope() -> TelemetryEnvelope:
    data = json.loads((ROOT / "contracts/examples/telemetry.normal.v1.json").read_text())
    return TelemetryEnvelope.model_validate(data)


def test_duplicate_message_is_idempotent(session_factory: sessionmaker[Session]) -> None:
    envelope = load_envelope()
    with session_factory() as session:
        first = persist_telemetry(session, envelope)
        second = persist_telemetry(session, envelope)
        row_count = session.scalar(select(func.count()).select_from(Telemetry))

    assert first.status == "inserted"
    assert second.status == "duplicate"
    assert row_count == 1


def test_sequence_collision_is_rejected(session_factory: sessionmaker[Session]) -> None:
    envelope = load_envelope()
    with session_factory() as session:
        persist_telemetry(session, envelope)
        colliding = envelope.model_copy(update={"message_id": uuid4()})
        with pytest.raises(SequenceCollisionError):
            persist_telemetry(session, colliding)
