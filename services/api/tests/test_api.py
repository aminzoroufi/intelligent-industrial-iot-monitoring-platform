# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

from __future__ import annotations

import json
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy.orm import Session, sessionmaker

from services.api.app.database import get_db
from services.api.app.main import create_app, safe_csv_text
from services.api.app.models import AnomalyModel
from services.api.app.settings import Settings

ROOT = Path(__file__).parents[3]


def build_client(factory: sessionmaker[Session]) -> AsyncClient:
    settings = Settings(
        jwt_secret=SecretStr("test-jwt-secret-with-at-least-32-characters"),
        ingest_token=SecretStr("test-ingest-token-with-at-least-32-characters"),
        demo_admin_password=SecretStr("local-test-password"),
    )
    app = create_app(settings)

    def override_db() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def login(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/auth/token",
        data={"username": "demo-admin", "password": "local-test-password"},
    )
    assert response.status_code == 200
    return str(response.json()["access_token"])


def current_query_window() -> dict[str, str]:
    now = datetime.now(UTC)
    return {
        "start": (now - timedelta(days=1)).isoformat(),
        "end": (now + timedelta(days=1)).isoformat(),
    }


@pytest.mark.asyncio
async def test_authentication_and_fleet_authorization(
    session_factory: sessionmaker[Session],
) -> None:
    async with build_client(session_factory) as client:
        assert (await client.get("/api/v1/devices")).status_code == 401
        assert (
            await client.post(
                "/api/v1/auth/token", data={"username": "demo-admin", "password": "wrong"}
            )
        ).status_code == 401

        token = await login(client)
        response = await client.get("/api/v1/devices", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        assert response.json()[0]["id"] == "motor-01"
        assert response.json()[0]["status"] == "offline"


@pytest.mark.asyncio
async def test_internal_ingestion_and_telemetry_query(
    session_factory: sessionmaker[Session],
) -> None:
    async with build_client(session_factory) as client:
        envelope = json.loads((ROOT / "contracts/examples/telemetry.normal.v1.json").read_text())

        assert (await client.post("/internal/v1/telemetry", json=envelope)).status_code == 422
        ingest = await client.post(
            "/internal/v1/telemetry",
            json=envelope,
            headers={"X-Ingest-Token": "test-ingest-token-with-at-least-32-characters"},
        )
        duplicate = await client.post(
            "/internal/v1/telemetry",
            json=envelope,
            headers={"X-Ingest-Token": "test-ingest-token-with-at-least-32-characters"},
        )

        token = await login(client)
        telemetry = await client.get(
            "/api/v1/devices/motor-01/telemetry",
            headers={"Authorization": f"Bearer {token}"},
            params={"start": "2020-01-01T00:00:00Z", "end": "2030-01-01T00:00:00Z"},
        )
        bounded = await client.get(
            "/api/v1/devices/motor-01/telemetry",
            headers={"Authorization": f"Bearer {token}"},
            params=current_query_window(),
        )

        assert ingest.json()["status"] == "inserted"
        assert duplicate.json()["status"] == "duplicate"
        assert telemetry.status_code == 422
        assert bounded.status_code == 200
        assert bounded.json()["count"] == 1


@pytest.mark.asyncio
async def test_anomaly_model_readiness_is_explicit(
    session_factory: sessionmaker[Session],
) -> None:
    async with build_client(session_factory) as client:
        token = await login(client)
        headers = {"Authorization": f"Bearer {token}"}

        missing = await client.get("/api/v1/devices/motor-01/anomaly-model", headers=headers)
        unknown = await client.get("/api/v1/devices/unknown/anomaly-model", headers=headers)
        assert missing.status_code == 200
        assert missing.json()["status"] == "model_not_ready"
        assert missing.json()["ready"] is False
        assert "MODEL_NOT_READY" in missing.json()["diagnostic"]
        assert unknown.status_code == 404

        now = datetime.now(UTC)
        with session_factory() as session:
            session.add(
                AnomalyModel(
                    device_id="motor-01",
                    model_version="iforest-v1-test",
                    status="ready",
                    feature_schema={"version": 1, "names": ["temperature_level_c"]},
                    training_start=now - timedelta(days=2),
                    training_end=now - timedelta(days=1),
                    training_sample_count=240,
                    validation_sample_count=60,
                    contamination=0.02,
                    random_seed=20260811,
                    sklearn_version="1.9.0",
                    artifact_path="motor-01/iforest-v1-test",
                    artifact_checksum="sha256:test",
                    created_at=now,
                )
            )
            session.commit()

        ready = await client.get("/api/v1/devices/motor-01/anomaly-model", headers=headers)
        assert ready.status_code == 200
        assert ready.json()["status"] == "ready"
        assert ready.json()["ready"] is True
        assert "artifact_path" not in ready.json()
        assert ready.json()["field_performance_claimed"] is False

        evaluation = await client.get("/api/v1/anomaly/evaluation-demo", headers=headers)
        assert evaluation.status_code == 200
        assert evaluation.json()["data_kind"] == "synthetic"
        assert evaluation.json()["field_performance_claimed"] is False


@pytest.mark.asyncio
async def test_operator_workflows_and_csv_export(
    session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "services.api.app.command_service.mqtt_publish.single", lambda *args, **kwargs: None
    )
    async with build_client(session_factory) as client:
        token = await login(client)
        headers = {"Authorization": f"Bearer {token}"}

        thresholds = await client.put(
            "/api/v1/devices/motor-01/thresholds",
            headers=headers,
            json={
                "temperature_warning_c": 60,
                "temperature_critical_c": 70,
                "vibration_warning_mps2": 4.5,
                "vibration_critical_mps2": 7,
                "current_warning_a": 1.4,
                "current_critical_a": 1.8,
                "hysteresis_percent": 5,
            },
        )
        assert thresholds.status_code == 200

        calibration = await client.post(
            "/api/v1/devices/motor-01/calibrations",
            headers=headers,
            json={
                "sensor": "temperature",
                "new_coefficients": {"scale": 1.01, "offset": -0.2},
                "reason": "Reference bath check",
            },
        )
        assert calibration.status_code == 201
        assert calibration.json()["previous_coefficients"] == {"scale": 1.0, "offset": 0.0}

        maintenance = await client.post(
            "/api/v1/devices/motor-01/maintenance",
            headers=headers,
            json={
                "status": "completed",
                "notes": "Inspected demo fixture and connector seating.",
                "performed_at": "2026-08-11T09:00:00Z",
                "next_due_at": "2026-09-11T09:00:00Z",
            },
        )
        assert maintenance.status_code == 201
        maintenance_id = maintenance.json()["id"]
        updated = await client.patch(
            f"/api/v1/maintenance/{maintenance_id}",
            headers=headers,
            json={"notes": "Inspection complete; no loose low-voltage wiring."},
        )
        assert updated.status_code == 200

        envelope = json.loads((ROOT / "contracts/examples/telemetry.normal.v1.json").read_text())
        envelope["measurements"]["temperature_c"] = 75.0
        ingest = await client.post(
            "/internal/v1/telemetry",
            json=envelope,
            headers={"X-Ingest-Token": "test-ingest-token-with-at-least-32-characters"},
        )
        assert ingest.status_code == 200

        alarms = await client.get(
            "/api/v1/alarms", headers=headers, params={"device_id": "motor-01", "state": "active"}
        )
        assert alarms.status_code == 200
        assert alarms.json()[0]["severity"] == "critical"
        acknowledged = await client.post(
            f"/api/v1/alarms/{alarms.json()[0]['id']}/acknowledge", headers=headers
        )
        assert acknowledged.json()["acknowledged_by"] == "demo-admin"

        exported = await client.get(
            "/api/v1/devices/motor-01/export.csv",
            headers=headers,
            params={
                "metric": "temperature_c",
                **current_query_window(),
            },
        )
        assert exported.status_code == 200
        assert "temperature_c,75.0" in exported.text

        command = await client.post(
            "/api/v1/devices/motor-01/commands/relay",
            headers=headers,
            json={"relay_on": True, "timeout_s": 5},
        )
        assert command.status_code == 202
        assert command.json()["status"] == "published"


def test_csv_formula_injection_guard() -> None:
    assert safe_csv_text("=1+1") == "'=1+1"
    assert safe_csv_text("normal") == "normal"
